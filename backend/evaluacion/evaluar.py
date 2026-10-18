"""Evaluación automática del tutor.

Corre conversaciones de prueba contra el tutor real (la misma función que usa
``POST /api/chat``) y revisa cada respuesta. Al final muestra un resumen por
tipo de revisión y guarda un reporte en ``evaluacion/resultados/``.

Hay dos conjuntos de casos:

- ``publico``: ``casos.json``, escritos a mano con problemas inventados.
- ``banco``: ``privado/casos_banco.json``, generados a partir del banco privado
  con ``python -m evaluacion.generar_casos``. Como el banco, no se suben al
  repositorio.

Uso, desde ``backend/``:

    .venv/bin/python -m evaluacion.evaluar               # todos los casos
    .venv/bin/python -m evaluacion.evaluar --caso no-se,otra-materia  # solo esos
    .venv/bin/python -m evaluacion.evaluar --conjunto banco --muestra 10  # 10 al azar del banco
    .venv/bin/python -m evaluacion.evaluar --proveedor groq  # solo Groq, para comparar parejo
    .venv/bin/python -m evaluacion.evaluar --juez gemini     # además, un juez con IA (ver juez.py)

La muestra usa una semilla fija (``--semilla``), así que repetirla da los mismos
casos: sirve para comparar dos versiones del tutor sin gastar la cuota de todos.

Las revisiones buscan patrones en el texto: detectan lo evidente (si confirmó,
si señaló el error, si volvió a preguntar algo ya respondido, si reveló la
respuesta, tuteo), no todo. Gasta cuota de los proveedores: cada turno es una
consulta.
"""

import argparse
import datetime
import json
import random
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.esquemas import AnotacionEnunciado, ChatEntrada, ChatSalida
from app.servicios import agente, modelos_ia, tutor
from app.servicios.modelos_ia import Proveedor, SinProveedores
from app.servicios.verificador import filtra_la_respuesta
from evaluacion import juez

CARPETA = Path(__file__).resolve().parent

# ---------- Casos ----------


class Turno(BaseModel):
    estudiante: str
    valora: Literal["bien", "mal"] | None = None
    """Qué debe decir el tutor de lo que propuso el estudiante: que está bien o que todavía no."""
    pista: bool | None = None
    """Si se espera que la respuesta sea (True) o no sea (False) una pista."""
    debe: list[str] = []
    """Patrones de los que al menos uno debe aparecer en la respuesta."""
    no_debe: list[str] = []
    """Patrones que no pueden aparecer."""
    no_debe_revelar: bool = False
    """Si en este turno el tutor no puede dejar ver la respuesta final."""
    felicita: Literal[False] | None = None
    """False si el estudiante no propuso nada ("no entendí"): el tutor no puede empezar felicitando."""


class Caso(BaseModel):
    id: str
    descripcion: str
    turnos: list[Turno]
    revelaria: list[str] = []
    """Patrones que delatan la respuesta final de este problema."""
    referencia: str | None = None
    """Clave y pasos del ejercicio, para el juez con IA (solo en los casos del banco)."""


RUTA_CASOS_PUBLICOS = CARPETA / "casos.json"
RUTA_CASOS_BANCO = CARPETA / "privado" / "casos_banco.json"


def cargar_casos(ruta: Path = RUTA_CASOS_PUBLICOS) -> list[Caso]:
    return [Caso.model_validate(c) for c in json.loads(ruta.read_text(encoding="utf-8"))]


def cargar_conjunto(conjunto: str) -> list[Caso]:
    """Los casos públicos, los generados del banco (si existen) o ambos."""
    casos = []
    if conjunto in ("publico", "todos"):
        casos += cargar_casos(RUTA_CASOS_PUBLICOS)
    if conjunto in ("banco", "todos") and RUTA_CASOS_BANCO.exists():
        casos += cargar_casos(RUTA_CASOS_BANCO)
    return casos


def muestra(casos: list[Caso], cuantos: int | None, semilla: int) -> list[Caso]:
    """Una muestra fija de los casos: con la misma semilla, siempre los mismos."""
    if not cuantos or cuantos >= len(casos):
        return casos
    return random.Random(semilla).sample(casos, cuantos)


# ---------- Revisiones (sin red: se pueden probar con pytest) ----------

ACIERTO = re.compile(
    r"(¡?\s*\b(eso(\s+es)?|exacto|correcto|muy bien|bien hecho|as[íi] es|perfecto|excelente|genial|buen[íi]simo)\b|^¡?\s*bien\b|[¡]\s*bien\b"
    r"|^¡?\s*dale\b)",  # "Dale, hacelo" acepta el paso que propuso el estudiante
    re.IGNORECASE,
)
ERROR = re.compile(
    r"(\b(todav[íi]a no|a[úu]n no|ojo|no es|no est[áa]|no da|cuidado|casi|no exactamente|no del todo|incorrect\w*|revis[áa]|f[íi]jate bien|no queda)\b"
    r"|^\W*no\b)",  # una respuesta que empieza con "No," también señala el error
    re.IGNORECASE,
)
# Formas del tuteo que el voseo dice distinto ("tenés", "fijate", "decime"...). Ojo: "fijate" sin
# tilde es voseo; solo "fíjate", con tilde, es tuteo.
TUTEO = re.compile(
    r"\b(haces|obtienes|puedes|tienes|piensa|fíjate|quieres|dime|sabes|necesitas|debes|intenta|recuerda|haz)\b"
    # En negativo el voseo también cambia: "no pongás", "no digás"; el tuteo es "no pongas", "no digas".
    r"|\bno\s+(?:te\s+|lo\s+|la\s+|me\s+)?(pongas|digas|hagas|tengas|pienses|olvides|uses|escribas|copies|compartas|dejes|preocupes|rindas)\b",
    re.IGNORECASE,
)
PROHIBIDAS = re.compile(r"\b(mae|pura vida)\b", re.IGNORECASE)


@dataclass
class Revision:
    nombre: str
    paso: bool
    detalle: str = ""


def revisar_turno(
    texto: str,
    pista: int | None,
    turno: Turno,
    revelaria: list[str],
    bloqueada: bool,
    es_el_problema: bool = False,
    apuntes: list[str] | tuple[str, ...] = (),
) -> list[Revision]:
    """Revisa una respuesta del tutor contra lo que se esperaba en ese turno.

    ``es_el_problema`` indica que el estudiante solo mandó el enunciado: ahí no
    propuso nada todavía, así que el tutor no tiene qué confirmar.
    ``apuntes`` son las líneas que el tutor escribió en la pizarra: la respuesta
    tampoco puede aparecer ahí.
    """
    revisiones: list[Revision] = []
    # Una felicitación cuenta solo al principio: "¡Eso es!" sí, "no puedo ayudar con eso" no.
    felicita_al_inicio = ACIERTO.search(texto[:40])
    if felicita_al_inicio and texto[: felicita_al_inicio.start()].strip(" ¡!¿,."):
        felicita_al_inicio = None

    if (es_el_problema and turno.valora is None) or turno.felicita is False:
        felicita = felicita_al_inicio
        revisiones.append(
            Revision("no felicita sin motivo", not felicita, f"empezó con «{felicita.group(0).strip()}»" if felicita else "")
        )

    if turno.valora == "bien":
        revisiones.append(Revision("confirma el acierto", bool(ACIERTO.search(texto)), "no dijo que estaba bien"))
    elif turno.valora == "mal":
        senala = bool(ERROR.search(texto)) and not felicita_al_inicio
        revisiones.append(Revision("señala el error", senala, "no dijo que todavía no estaba bien"))

    if turno.pista is True:
        revisiones.append(Revision("da una pista", pista is not None, "no la marcó como pista"))
    elif turno.pista is False:
        revisiones.append(Revision("no marca pista", pista is None, f"la marcó como pista {pista}"))

    for patron in turno.debe:
        revisiones.append(Revision("dice lo esperado", bool(re.search(patron, texto, re.I)), f"falta /{patron}/"))
    for patron in turno.no_debe:
        hallado = re.search(patron, texto, re.I)
        revisiones.append(
            Revision("no repite ni se adelanta", not hallado, f"dijo «{hallado.group(0)}»" if hallado else "")
        )

    if turno.no_debe_revelar:
        # La respuesta no puede aparecer ni en el chat ni en la pizarra.
        donde = " \n".join([texto, *apuntes])
        delata = next((p for p in revelaria if re.search(p, donde, re.I)), None)
        revisiones.append(Revision("no revela la respuesta", delata is None and not bloqueada, f"/{delata}/" if delata else "el verificador tuvo que bloquearla"))

    tuteo = TUTEO.search(texto)
    revisiones.append(Revision("voseo sin tuteo", not tuteo, f"dijo «{tuteo.group(0)}»" if tuteo else ""))
    prohibida = PROHIBIDAS.search(texto)
    revisiones.append(Revision("sin 'mae' ni 'pura vida'", not prohibida, f"dijo «{prohibida.group(0)}»" if prohibida else ""))
    return revisiones


# ---------- Ejecución con el tutor real ----------


@dataclass
class ResultadoTurno:
    estudiante: str
    texto: str
    pista: int | None
    proveedor: str
    revisiones: list[Revision] = field(default_factory=list)


def _responder_con_paciencia(entrada: ChatEntrada, intentos: int = 6) -> ChatSalida:
    """Llama al tutor; si los proveedores están saturados o sin cuota, espera y reintenta."""
    for intento in range(intentos):
        try:
            return tutor.responder(entrada)
        except SinProveedores:
            if intento == intentos - 1:
                raise
            time.sleep(15 * (intento + 1))
    raise AssertionError("inalcanzable")


def correr_caso(caso: Caso, pausa: float) -> list[ResultadoTurno]:
    historial: list[dict] = []
    enunciado: str | None = None
    pistas = 0
    resultados = []
    for turno in caso.turnos:
        entrada = ChatEntrada(
            mensaje=turno.estudiante,
            historial=historial,
            contexto={"enunciado": enunciado, "pistas_dadas": pistas},
        )
        salida = _responder_con_paciencia(entrada)
        bloqueada = salida.texto == tutor.RESPUESTA_SEGURA or filtra_la_respuesta(salida, entrada)
        resultado = ResultadoTurno(turno.estudiante, salida.texto, salida.pista, salida.proveedor)
        apuntes = [a.texto for a in salida.anotaciones if a.tipo == "apunte"]
        resultado.revisiones = revisar_turno(
            salida.texto,
            salida.pista,
            turno,
            caso.revelaria,
            bloqueada,
            es_el_problema=enunciado is None and not historial,
            apuntes=apuntes,
        )
        resultados.append(resultado)

        historial += [
            {"autor": "estudiante", "texto": turno.estudiante},
            {"autor": "tutor", "texto": salida.texto, "pista": salida.pista},
        ]
        enunciado = next((a.texto for a in salida.anotaciones if isinstance(a, AnotacionEnunciado)), enunciado)
        pistas += 1 if salida.pista else 0
        time.sleep(pausa)
    return resultados


def elegir_proveedores(disponibles: list[Proveedor], filtro: str | None) -> list[Proveedor]:
    """Deja solo los proveedores que coinciden con el filtro: un nombre ("groq") o un modelo
    ("gemini/gemini-3.5-flash" o "gemini-3.5-flash"). Sin filtro, deja la cadena completa."""
    if not filtro:
        return disponibles
    filtro = filtro.strip().lower()
    return [p for p in disponibles if filtro in (p.nombre, p.etiqueta.lower(), p.modelo.lower())]


def _reporte(
    resultados: dict[str, list[ResultadoTurno]], casos: dict[str, Caso], proveedores: list[Proveedor]
) -> tuple[str, Counter, Counter]:
    pasaron, totales = Counter(), Counter()
    cadena = " → ".join(f"{p.etiqueta} ({p.modelo})" for p in proveedores)
    lineas = [
        f"# Evaluación del tutor — {datetime.datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"- Proveedores: {cadena}",
        f"- Instrucciones del tutor: {len(agente.INSTRUCCIONES_DEL_TUTOR)} caracteres",
        "",
    ]
    for caso_id, turnos in resultados.items():
        lineas += [f"## {caso_id}", "", casos[caso_id].descripcion, ""]
        for r in turnos:
            lineas.append(f"- **Estudiante:** {r.estudiante}")
            lineas.append(f"  - **Tutor** ({r.proveedor}, pista={r.pista}): {r.texto}")
            for rev in r.revisiones:
                totales[rev.nombre] += 1
                pasaron[rev.nombre] += rev.paso
                if not rev.paso:
                    lineas.append(f"  - ✗ {rev.nombre}: {rev.detalle}")
        lineas.append("")
    lineas += ["## Resumen", "", "| Revisión | Pasó |", "| --- | --- |"]
    for nombre in totales:
        lineas.append(f"| {nombre} | {pasaron[nombre]} de {totales[nombre]} |")
    total_paso, total = sum(pasaron.values()), sum(totales.values())
    lineas += ["", f"**Total: {total_paso} de {total} ({100 * total_paso / max(total, 1):.0f} %)**", ""]
    return "\n".join(lineas), pasaron, totales


def main(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description="Evalúa al tutor con conversaciones de prueba.")
    opciones.add_argument("--caso", help="Correr solo estos casos (ids separados por coma).")
    opciones.add_argument(
        "--conjunto", choices=("publico", "banco", "todos"), default="todos", help="Qué casos correr."
    )
    opciones.add_argument("--muestra", type=int, help="Correr solo esta cantidad de casos, elegidos al azar.")
    opciones.add_argument("--semilla", type=int, default=2026, help="Semilla de la muestra.")
    opciones.add_argument(
        "--juez", help='Calificar además con un juez de IA de este proveedor ("gemini", "groq" o un modelo). Una consulta por caso.'
    )
    opciones.add_argument("--pausa", type=float, default=4.0, help="Segundos entre turnos, para no agotar la cuota.")
    opciones.add_argument(
        "--proveedor",
        help='Usar un solo proveedor, para que las comparaciones sean parejas: "groq", "gemini" o un modelo.',
    )
    args = opciones.parse_args(argumentos)

    casos = {c.id: c for c in cargar_conjunto(args.conjunto)}
    if args.conjunto == "banco" and not casos:
        print("No hay casos del banco. Generalos con: python -m evaluacion.generar_casos")
        return 2
    if args.caso:
        pedidos = [c.strip() for c in args.caso.split(",") if c.strip()]
        desconocidos = [c for c in pedidos if c not in casos]
        if desconocidos:
            print(f"No existen los casos: {', '.join(desconocidos)}. Disponibles: {', '.join(casos)}.")
            return 2
        elegidos = [casos[c] for c in pedidos]
    else:
        elegidos = muestra(list(casos.values()), args.muestra, args.semilla)
    proveedores = elegir_proveedores(modelos_ia.proveedores_disponibles(), args.proveedor)
    if not proveedores:
        nombres = ", ".join(p.etiqueta for p in modelos_ia.proveedores_disponibles()) or "ninguno"
        print(f"No hay ningún proveedor «{args.proveedor}» con llave. Disponibles: {nombres}.")
        return 2
    jueces = elegir_proveedores(modelos_ia.proveedores_disponibles(), args.juez) if args.juez else []
    if args.juez and not jueces:
        print(f"No hay ningún proveedor «{args.juez}» con llave para el juez.")
        return 2
    completar_original = modelos_ia.completar
    modelos_ia.completar = lambda mensajes, **kw: completar_original(mensajes, **{"proveedores": proveedores, **kw})
    print("Proveedores: " + " → ".join(p.etiqueta for p in proveedores), flush=True)
    if jueces:
        print("Juez: " + " → ".join(p.etiqueta for p in jueces), flush=True)

    resultados: dict[str, list[ResultadoTurno]] = {}
    for caso in elegidos:
        print(f"→ {caso.id} ({len(caso.turnos)} turnos)…", flush=True)
        try:
            resultados[caso.id] = correr_caso(caso, args.pausa)
        except SinProveedores as error:
            print(f"  sin respuesta de los proveedores: {error}", flush=True)
        else:
            if jueces:
                turnos = [(r.estudiante, r.texto) for r in resultados[caso.id]]
                for r, calificaciones in zip(resultados[caso.id], juez.juzgar(turnos, caso.referencia, jueces)):
                    r.revisiones += [Revision(c.nombre, c.paso, c.detalle) for c in calificaciones]
            fallas = [rev for r in resultados[caso.id] for rev in r.revisiones if not rev.paso]
            print(f"  {'✓ todo bien' if not fallas else f'✗ {len(fallas)} revisiones fallaron'}", flush=True)

    modelos_ia.completar = completar_original
    texto, pasaron, totales = _reporte(resultados, casos, proveedores)
    carpeta = CARPETA / "resultados"
    carpeta.mkdir(exist_ok=True)
    archivo = carpeta / f"{datetime.datetime.now():%Y-%m-%d_%H%M}.md"
    archivo.write_text(texto, encoding="utf-8")
    print()
    for nombre in totales:
        print(f"  {nombre:28} {pasaron[nombre]:>3} de {totales[nombre]}")
    print(f"\nTotal: {sum(pasaron.values())} de {sum(totales.values())}. Reporte: {archivo}")
    return 0 if resultados else 1


if __name__ == "__main__":
    sys.exit(main())
