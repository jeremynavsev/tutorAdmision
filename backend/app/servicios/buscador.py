"""Búsqueda de ejercicios parecidos en el banco (la parte de "consulta" del RAG).

Cuando el estudiante trae un problema, se buscan en el banco los ejercicios más
parecidos y se le pasan al tutor, en privado, sus pasos y errores comunes. Si
el problema es uno del banco, además se usa su clave para que el verificador
detecte si el tutor la regala.

La búsqueda es léxica (TF-IDF con similitud de coseno), en Python puro: el
banco tiene cientos de ejercicios, no millones, y así no hace falta otra
dependencia ni mandar el problema a un servicio de embeddings. Antes de
comparar se pasa todo a minúsculas, sin tildes y sin palabras vacías ("el",
"de", "que"…).

Para decir que es *el mismo* ejercicio no basta con que se parezca:

- tienen que aparecer casi todas sus palabras y todos sus números;
- el problema no puede traer números que el ejercicio no tiene (así una
  sucesión con otros términos no pasa por la del banco);
- si el problema trae las opciones, tienen que ser las mismas y en el mismo
  orden: otra versión del ítem puede tener otra clave.

Un ejercicio parecido que no cumple esto no es el mismo, y su clave no sirve
para verificar. Los subíndices y exponentes se normalizan antes de comparar:
"N₁₁₆" es "N116" y "2²" es "2^2".
"""

import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from app.datos.banco import BancoInvalido, cargar_banco
from app.esquemas import Ejercicio

registro = logging.getLogger(__name__)

PARECIDOS_POR_CONSULTA = 2
SIMILITUD_MINIMA = 0.2
"""Por debajo de esto, un ejercicio no ayuda: es mejor no pasar nada que pasar ruido."""
COBERTURA_MISMO_EJERCICIO = 0.8
"""Fracción de las palabras del ejercicio del banco que deben aparecer en el problema."""
NUMEROS_AJENOS_PERMITIDOS = 1
"""Números del problema que no están en el ejercicio (por ejemplo, "el ítem 12 de la práctica")."""
SIMILITUD_OPCION = 0.7
"""Palabras en común entre la opción del banco y la del problema, sobre todas las palabras de las dos.

Se mide en las dos direcciones: las opciones son cortas y comparten palabras ("Observar y andar…",
"Andar es más… que observar"), así que no basta con que una contenga a la otra."""

_PALABRAS_VACIAS = set(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada como con contra cual cuales
    cuando de del desde donde dos e el ella ellas ellos en entre era es esa esas ese eso esos esta estas este
    esto estos fue ha hay la las le les lo los mas me mi muy no nos o otra otras otro otros para pero por porque
    que se ser si sin sobre son su sus tambien te tiene tienen todo todos tu un una uno unos y ya
    """.split()
)
_PALABRA = re.compile(r"[a-zñ]+|\d+")
_EXPONENTES = str.maketrans({"⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9"})
# Una opción: "A) …" al inicio de una línea o después de un espacio, con las letras en orden.
_MARCA_DE_OPCION = re.compile(r"(?:^|(?<=\s))\(?([A-E])\)\s*", re.MULTILINE)


def _sin_tildes(texto: str) -> str:
    # Se descompone para quitar las tildes, pero la ñ se conserva.
    texto = texto.lower().replace("ñ", "\0")
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.replace("\0", "ñ")


def _normalizado(texto: str) -> str:
    """Exponentes como "^2" y subíndices y letras matemáticas como texto común ("𝑁₁" → "N1")."""
    return unicodedata.normalize("NFKC", texto.translate(_EXPONENTES))


def palabras(texto: str) -> list[str]:
    """Las palabras que cuentan para comparar: sin tildes, sin palabras vacías, con los números."""
    texto = _normalizado(texto)
    texto = re.sub(r"(?<=\d)[  .](?=\d{3}(?!\d))", "", texto)  # "3 000" y "3.000" son el mismo número
    return [p for p in _PALABRA.findall(_sin_tildes(texto)) if p.isdigit() or (len(p) > 2 and p not in _PALABRAS_VACIAS)]


def opciones_del_texto(texto: str) -> list[str]:
    """Las opciones que trae el problema ("A) 9", "B) 10"…), si vienen en orden desde la A."""
    marcas = list(_MARCA_DE_OPCION.finditer(texto))
    opciones = []
    for i, marca in enumerate(marcas):
        if marca.group(1) != "ABCDE"[len(opciones)]:
            break
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        opciones.append(texto[marca.end() : fin].strip())
    return opciones if len(opciones) >= 2 else []


def _misma_opcion(del_banco: str, del_problema: str) -> bool:
    propias, presentes = set(palabras(del_banco)), set(palabras(del_problema))
    if not propias:  # una opción sin palabras que cuenten ("—"): se compara el texto tal cual
        return del_banco.strip(" .") == del_problema.strip(" .")
    return len(propias & presentes) / len(propias | presentes) >= SIMILITUD_OPCION


@dataclass(frozen=True)
class Coincidencia:
    ejercicio: Ejercicio
    similitud: float


class Buscador:
    """Índice TF-IDF del banco, armado una vez al cargarlo."""

    def __init__(self, ejercicios: list[Ejercicio] | tuple[Ejercicio, ...]):
        self.ejercicios = list(ejercicios)
        documentos = [palabras(self._texto(e)) for e in self.ejercicios]
        total = len(documentos)
        aparece_en = Counter(p for doc in documentos for p in set(doc))
        self._idf = {p: math.log((1 + total) / (1 + n)) + 1 for p, n in aparece_en.items()}
        self._vectores = [self._vector(doc) for doc in documentos]
        self._propias = {e.id: set(palabras(e.enunciado)) for e in self.ejercicios}
        self._numeros = {e.id: {p for p in palabras(self._texto(e)) if p.isdigit()} for e in self.ejercicios}

    @staticmethod
    def _texto(ejercicio: Ejercicio) -> str:
        # Con saltos de línea y no con espacios: "35 49 168" se leería como un número con miles.
        return "\n".join([ejercicio.tema, ejercicio.enunciado, *ejercicio.opciones])

    def _vector(self, doc: list[str]) -> dict[str, float]:
        cuentas = Counter(doc)
        # Una palabra que no está en el banco no ayuda a comparar.
        vector = {p: (1 + math.log(n)) * self._idf[p] for p, n in cuentas.items() if p in self._idf}
        norma = math.sqrt(sum(v * v for v in vector.values()))
        return {p: v / norma for p, v in vector.items()} if norma else {}

    def buscar(self, texto: str, cuantos: int = PARECIDOS_POR_CONSULTA, minimo: float = SIMILITUD_MINIMA) -> list[Coincidencia]:
        """Los ejercicios más parecidos al texto, del más al menos parecido."""
        consulta = self._vector(palabras(texto))
        if not consulta:
            return []
        puntajes = [
            Coincidencia(e, sum(peso * vector.get(p, 0.0) for p, peso in consulta.items()))
            for e, vector in zip(self.ejercicios, self._vectores)
        ]
        buenos = [c for c in puntajes if c.similitud >= minimo]
        return sorted(buenos, key=lambda c: c.similitud, reverse=True)[:cuantos]

    def mismo_ejercicio(self, texto: str) -> Ejercicio | None:
        """El ejercicio del banco que es este mismo problema, si hay uno."""
        presentes = set(palabras(texto))
        numeros_del_problema = {p for p in presentes if p.isdigit()}
        opciones = opciones_del_texto(texto)
        for c in self.buscar(texto, cuantos=3):
            e = c.ejercicio
            propias = self._propias[e.id]
            if not propias or not {p for p in propias if p.isdigit()} <= presentes:
                continue  # le faltan números del ejercicio
            if len(numeros_del_problema - self._numeros[e.id]) > NUMEROS_AJENOS_PERMITIDOS:
                continue  # trae números que el ejercicio no tiene
            if len(propias & presentes) / len(propias) < COBERTURA_MISMO_EJERCICIO:
                continue
            if opciones and not self._mismas_opciones(e, opciones):
                continue  # otra versión del ítem: su clave puede ser otra
            return e
        return None

    @staticmethod
    def _mismas_opciones(ejercicio: Ejercicio, opciones: list[str]) -> bool:
        return len(opciones) == len(ejercicio.opciones) and all(
            _misma_opcion(del_banco, del_problema) for del_banco, del_problema in zip(ejercicio.opciones, opciones)
        )


@lru_cache
def obtener_buscador() -> Buscador:
    """El buscador del banco configurado. Si el banco no se puede leer, el tutor sigue sin él."""
    try:
        return Buscador(cargar_banco())
    except BancoInvalido as error:
        registro.error("No se pudo cargar el banco de ejercicios; el tutor seguirá sin él: %s", error)
        return Buscador([])
