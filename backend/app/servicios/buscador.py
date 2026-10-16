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

Para decir que es *el mismo* ejercicio no basta con que se parezca: tienen que
aparecer casi todas sus palabras y todos sus números. Un ejercicio parecido
con otros números no es el mismo, y su clave no sirve para verificar.
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

_PALABRAS_VACIAS = set(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada como con contra cual cuales
    cuando de del desde donde dos e el ella ellas ellos en entre era es esa esas ese eso esos esta estas este
    esto estos fue ha hay la las le les lo los mas me mi muy no nos o otra otras otro otros para pero por porque
    que se ser si sin sobre son su sus tambien te tiene tienen todo todos tu un una uno unos y ya
    """.split()
)
_PALABRA = re.compile(r"[a-zñ]+|\d+")


def _sin_tildes(texto: str) -> str:
    # Se descompone para quitar las tildes, pero la ñ se conserva.
    texto = texto.lower().replace("ñ", "\0")
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.replace("\0", "ñ")


def palabras(texto: str) -> list[str]:
    """Las palabras que cuentan para comparar: sin tildes, sin palabras vacías, con los números."""
    texto = re.sub(r"(?<=\d)[  .](?=\d{3}(?!\d))", "", texto)  # "3 000" y "3.000" son el mismo número
    return [p for p in _PALABRA.findall(_sin_tildes(texto)) if p.isdigit() or (len(p) > 2 and p not in _PALABRAS_VACIAS)]


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

    @staticmethod
    def _texto(ejercicio: Ejercicio) -> str:
        return " ".join([ejercicio.tema, ejercicio.enunciado, *ejercicio.opciones])

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
        for c in self.buscar(texto, cuantos=3):
            propias = self._propias[c.ejercicio.id]
            numeros = {p for p in propias if p.isdigit()}
            if not propias or not numeros <= presentes:
                continue
            if len(propias & presentes) / len(propias) >= COBERTURA_MISMO_EJERCICIO:
                return c.ejercicio
        return None


@lru_cache
def obtener_buscador() -> Buscador:
    """El buscador del banco configurado. Si el banco no se puede leer, el tutor sigue sin él."""
    try:
        return Buscador(cargar_banco())
    except BancoInvalido as error:
        registro.error("No se pudo cargar el banco de ejercicios; el tutor seguirá sin él: %s", error)
        return Buscador([])
