"""Verificación de respuestas con SymPy.

Compara lo que propone el estudiante con la solución del ejercicio
(equivalencia simbólica o numérica, o letra de opción) y revisa que el tutor
no haya filtrado la respuesta final en su mensaje.
"""

from app.esquemas import Solucion


def es_equivalente(propuesta: str, solucion: Solucion) -> bool:
    """Indica si la propuesta del estudiante coincide con la solución."""
    raise NotImplementedError


def revela_solucion(texto_del_tutor: str, solucion: Solucion) -> bool:
    """Detecta si un mensaje del tutor contiene la respuesta final."""
    raise NotImplementedError
