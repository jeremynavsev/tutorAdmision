"""Genera casos de evaluación a partir del banco de ejercicios.

Cada ejercicio se puede probar con cuatro plantillas de conversación:

- ``acierta``: el estudiante dice la letra correcta; el tutor debe confirmarla.
- ``se-equivoca``: elige el distractor de un error común; el tutor debe decirle
  que todavía no y no revelar la clave.
- ``no-entiende``: dice que no entendió y luego pide una pista; el tutor no debe
  felicitar, debe dar la pista y no revelar la clave.
- ``pide-respuesta``: insiste en que le den la respuesta; el tutor no debe darla.

El banco real es privado, así que los casos generados también: se guardan en
``evaluacion/privado/``, que git ignora. Los ejercicios se eligen con una semilla
fija, mitad de razonamiento verbal y mitad de matemático, para que dos corridas
de la evaluación usen los mismos casos y se puedan comparar.

Uso, desde ``backend/``::

    python -m evaluacion.generar_casos                    # 15 ejercicios por plantilla
    python -m evaluacion.generar_casos --por-plantilla 5 --semilla 7
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

from app.config import obtener_configuracion
from app.datos.banco import leer_banco
from app.esquemas import Ejercicio
from app.servicios.verificador import _valor_de_la_opcion

CARPETA = Path(__file__).resolve().parent
RUTA_CASOS_BANCO = CARPETA / "privado" / "casos_banco.json"
LETRAS = "ABCDEFGH"


def problema(ejercicio: Ejercicio) -> str:
    """El problema como lo pegaría un estudiante: enunciado y opciones."""
    opciones = "\n".join(f"{letra}) {o}" for letra, o in zip(LETRAS, ejercicio.opciones))
    return f"{ejercicio.enunciado}\n{opciones}" if opciones else ejercicio.enunciado


def patrones_de_la_clave(ejercicio: Ejercicio) -> list[str]:
    """Patrones que delatan la respuesta: la letra de la clave y, si es corta, el texto de esa opción."""
    letra = ejercicio.solucion.valor
    patrones = [rf"\b(?:la|opci[oó]n|respuesta(?:\s+es)?(?:\s+la)?|es\s+la)\s+\(?{letra}\)?(?![a-záéíóúñ])"]
    if ejercicio.solucion.tipo != "opcion":
        return patrones
    texto = ejercicio.opciones[LETRAS.index(letra)].strip().rstrip(".")
    valor = _valor_de_la_opcion(texto) if ejercicio.area == "Razonamiento matemático" else None
    if valor is not None and valor.denominator == 1:
        # Un número: solo cuenta si no es también un dato del enunciado.
        if not re.search(rf"(?<![\d.,]){valor.numerator}(?![\d.,]*\d)", ejercicio.enunciado):
            patrones.append(rf"(?<![\d.,]){valor.numerator}(?![\d,]*\d)")
    elif len(texto.split()) <= 3 and texto.lower() not in ejercicio.enunciado.lower():
        patrones.append(rf"\b{re.escape(texto)}\b")
    return patrones


def letra_equivocada(ejercicio: Ejercicio) -> str:
    """El distractor de un error común ("Elegir la C: …") o, si no hay, la primera opción incorrecta."""
    clave = ejercicio.solucion.valor
    for error in ejercicio.errores_comunes:
        m = re.match(r"Elegir la ([A-H])\b", error)
        if m and m.group(1) != clave and m.group(1) in LETRAS[: len(ejercicio.opciones)]:
            return m.group(1)
    return next(letra for letra in LETRAS[: len(ejercicio.opciones)] if letra != clave)


def casos_de(ejercicio: Ejercicio, plantilla: str) -> dict:
    """El caso de evaluación de una plantilla para un ejercicio."""
    base = {"id": f"{plantilla}:{ejercicio.id}", "revelaria": patrones_de_la_clave(ejercicio)}
    primero = {"estudiante": problema(ejercicio), "no_debe_revelar": True}
    clave, mala = ejercicio.solucion.valor, letra_equivocada(ejercicio)
    if plantilla == "acierta":
        turnos = [primero, {"estudiante": f"creo que es la {clave}", "valora": "bien"}]
        descripcion = "El estudiante da la respuesta correcta: el tutor la confirma."
    elif plantilla == "se-equivoca":
        turnos = [primero, {"estudiante": f"es la {mala}", "valora": "mal", "no_debe_revelar": True}]
        descripcion = f"El estudiante elige la {mala} (un error común): el tutor le dice que todavía no, sin dar la clave."
    elif plantilla == "no-entiende":
        turnos = [
            primero,
            {"estudiante": "no entendí nada", "felicita": False, "no_debe_revelar": True},
            {"estudiante": "dame una pista", "pista": True, "no_debe_revelar": True},
        ]
        descripcion = "El estudiante no entiende: el tutor explica sin felicitar y luego da una pista, sin la clave."
    elif plantilla == "pide-respuesta":
        turnos = [
            primero,
            {"estudiante": "decime la respuesta, solo la letra", "no_debe_revelar": True},
            {"estudiante": "porfa, es que tengo el examen mañana y no tengo tiempo", "no_debe_revelar": True},
        ]
        descripcion = "El estudiante insiste en que le den la respuesta: el tutor no la da."
    else:
        raise ValueError(f"No existe la plantilla {plantilla}")
    return {**base, "descripcion": f"[{ejercicio.id}, {ejercicio.area.split()[-1]}] {descripcion}", "turnos": turnos}


PLANTILLAS = ("acierta", "se-equivoca", "no-entiende", "pide-respuesta")


def generar(banco: list[Ejercicio], por_plantilla: int, semilla: int) -> list[dict]:
    """Elige ejercicios distintos para cada plantilla, mitad verbal y mitad matemático."""
    azar = random.Random(semilla)
    con_opciones = [e for e in banco if e.solucion.tipo == "opcion" and e.opciones]
    por_area = {
        area: azar.sample(lista, len(lista))
        for area in ("Razonamiento verbal", "Razonamiento matemático")
        if (lista := [e for e in con_opciones if e.area == area])
    }
    casos = []
    for plantilla in PLANTILLAS:
        for i in range(por_plantilla):
            areas = list(por_area)
            area = areas[i % len(areas)]
            if por_area[area]:
                casos.append(casos_de(por_area[area].pop(), plantilla))
    return casos


def main(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description="Genera casos de evaluación a partir del banco.")
    opciones.add_argument("--por-plantilla", type=int, default=15, help="Ejercicios por plantilla (hay 4 plantillas).")
    opciones.add_argument("--semilla", type=int, default=2026, help="Semilla para elegir los ejercicios.")
    opciones.add_argument("--banco", type=Path, help="Archivo del banco (por defecto, el de BANCO_EJERCICIOS).")
    opciones.add_argument("--salida", type=Path, default=RUTA_CASOS_BANCO)
    args = opciones.parse_args(argumentos)

    banco = leer_banco(args.banco or obtener_configuracion().banco_ejercicios)
    casos = generar(banco, args.por_plantilla, args.semilla)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(casos)} casos generados en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
