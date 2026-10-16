"""Revisión del banco de ejercicios.

Cada ejercicio puede traer una ``comprobacion``: un cálculo hecho por aparte (por
ejemplo ``94 - (48 - 36/4)``) que da la respuesta correcta. Esta revisión lo
calcula con SymPy y lo compara con la opción marcada como clave. Así se detecta
una clave mal transcrita, o un ejercicio en el que dos opciones dan lo mismo.

Las opciones se leen como número ("50 gapes" → 50) o como expresión
("65 + 16²", "S₁₀ + 23"). Las que son frases no se pueden comparar: esos
ejercicios, igual que los de razonamiento verbal, quedan para revisión humana.

Uso, desde ``backend/``::

    python -m app.datos.revision            # el banco configurado en BANCO_EJERCICIOS
    python -m app.datos.revision ruta.json  # otro archivo

Termina con código 1 si alguna comprobación falla.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import sympy
from sympy.parsing.sympy_parser import convert_xor, parse_expr, rationalize, standard_transformations

from app.config import obtener_configuracion
from app.datos.banco import BancoInvalido, leer_banco
from app.esquemas import Ejercicio

# Funciones que se pueden usar en una comprobación. Ningún otro nombre se acepta.
_FUNCIONES = {
    "igcd": sympy.igcd,
    "ilcm": sympy.ilcm,
    "Mod": sympy.Mod,
    "floor": sympy.floor,
    "ceiling": sympy.ceiling,
    "binomial": sympy.binomial,
    "factorial": sympy.factorial,
    "sqrt": sympy.sqrt,
}
# Una letra mayúscula con subíndice ("S10", "N115") es una incógnita.
_INCOGNITA = re.compile(r"[A-Z]\d*")
_NOMBRE = re.compile(r"[A-Za-z_]\w*")
_SUBINDICES = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_POTENCIAS = {"²": "^2", "³": "^3"}
_NUMERO_EN_FRASE = re.compile(r"\d{1,3}(?:[  .]\d{3})+(?:,\d+)?(?!\d)|\d+(?:,\d+)?")


class ComprobacionInvalida(Exception):
    """La comprobación usa algo que no está permitido o SymPy no la entiende."""


def _normalizar(texto: str) -> str:
    """Pasa la notación de los ejercicios (−, ×, ², S₁₀, 3 000, 2,5) a la de SymPy."""
    t = texto.strip().rstrip(".").translate(_SUBINDICES)
    for potencia, reemplazo in _POTENCIAS.items():
        t = t.replace(potencia, reemplazo)
    t = t.replace("−", "-").replace("×", "*").replace("·", "*").replace("÷", "/").replace(" ", " ")
    t = re.sub(r"(?<=\d)[ .](?=\d{3}(?!\d))", "", t)  # separadores de miles
    return re.sub(r"(?<=\d),(?=\d)", ".", t)  # coma decimal


def _a_sympy(texto: str) -> sympy.Expr:
    """Calcula una expresión con números, incógnitas como S10 y las funciones permitidas."""
    t = _normalizar(texto)
    if not re.fullmatch(r"[\w+\-*/^(), .]+", t):
        raise ComprobacionInvalida(f"Tiene caracteres que no se permiten: {texto!r}")
    nombres = {}
    for nombre in _NOMBRE.findall(t):
        if nombre in _FUNCIONES:
            nombres[nombre] = _FUNCIONES[nombre]
        elif _INCOGNITA.fullmatch(nombre):
            nombres[nombre] = sympy.Symbol(nombre)
        else:
            raise ComprobacionInvalida(f"El nombre {nombre!r} no está permitido en {texto!r}")
    try:
        valor = parse_expr(t, local_dict=nombres, transformations=standard_transformations + (convert_xor, rationalize))
    except Exception as error:  # cualquier cosa que SymPy no entienda
        raise ComprobacionInvalida(f"SymPy no entiende {texto!r}: {error}") from error
    if not isinstance(valor, sympy.Expr):
        raise ComprobacionInvalida(f"{texto!r} no da un valor.")
    return valor


def valor_de_opcion(opcion: str) -> sympy.Expr | None:
    """El valor de una opción: como expresión ("65 + 16²") o el único número de una frase ("50 gapes")."""
    try:
        return _a_sympy(opcion)
    except ComprobacionInvalida:
        numeros = _NUMERO_EN_FRASE.findall(opcion)
        return _a_sympy(numeros[0]) if len(numeros) == 1 else None


def _iguales(a: sympy.Expr, b: sympy.Expr) -> bool:
    return sympy.simplify(a - b) == 0


@dataclass(frozen=True)
class Resultado:
    id: str
    estado: str
    """``verificado``, ``error`` o ``sin_comprobacion``."""
    detalle: str = ""


def revisar_ejercicio(ejercicio: Ejercicio) -> Resultado:
    """Compara la comprobación del ejercicio con su clave."""
    if not ejercicio.comprobacion:
        return Resultado(ejercicio.id, "sin_comprobacion")
    try:
        esperado = _a_sympy(ejercicio.comprobacion)
    except ComprobacionInvalida as error:
        return Resultado(ejercicio.id, "error", str(error))

    solucion = ejercicio.solucion
    if solucion.tipo != "opcion":
        clave = valor_de_opcion(solucion.valor)
        if clave is None or not _iguales(esperado, clave):
            return Resultado(ejercicio.id, "error", f"La comprobación da {esperado} y la solución dice {solucion.valor}.")
        return Resultado(ejercicio.id, "verificado")

    letras = "ABCDEFGH"
    coinciden = [letras[i] for i, op in enumerate(ejercicio.opciones) if (v := valor_de_opcion(op)) is not None and _iguales(esperado, v)]
    if coinciden == [solucion.valor]:
        return Resultado(ejercicio.id, "verificado")
    if not coinciden:
        return Resultado(ejercicio.id, "error", f"La comprobación da {esperado} y no coincide con ninguna opción.")
    if solucion.valor not in coinciden:
        return Resultado(ejercicio.id, "error", f"La comprobación da {esperado}, que es la opción {', '.join(coinciden)}, pero la clave es {solucion.valor}.")
    return Resultado(ejercicio.id, "error", f"La comprobación da {esperado} y coinciden varias opciones: {', '.join(coinciden)}.")


def informe(ejercicios: list[Ejercicio]) -> tuple[str, bool]:
    """El texto del informe y si todo salió bien."""
    resultados = [revisar_ejercicio(e) for e in ejercicios]
    errores = [r for r in resultados if r.estado == "error"]
    verificados = [r.id for r in resultados if r.estado == "verificado"]
    sin_comprobar = [r.id for r in resultados if r.estado == "sin_comprobacion"]
    sin_revisar = [e.id for e in ejercicios if not e.revisado]

    lineas = [f"{len(ejercicios)} ejercicios en el banco.", f"Verificados con SymPy: {len(verificados)}."]
    if errores:
        lineas.append(f"Con errores: {len(errores)}.")
        lineas += [f"  ✗ {r.id}: {r.detalle}" for r in errores]
    lineas.append(f"Sin comprobación automática: {len(sin_comprobar)}." + (f" {', '.join(sin_comprobar)}" if sin_comprobar else ""))
    lineas.append(f"Pendientes de revisión humana: {len(sin_revisar)}." + (f" {', '.join(sin_revisar)}" if sin_revisar else ""))
    return "\n".join(lineas), not errores


def main(argumentos: list[str]) -> int:
    ruta = Path(argumentos[0]) if argumentos else obtener_configuracion().banco_ejercicios
    try:
        ejercicios = leer_banco(ruta)
    except BancoInvalido as error:
        print(f"✗ {error}")
        return 1
    texto, bien = informe(ejercicios)
    print(texto)
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
