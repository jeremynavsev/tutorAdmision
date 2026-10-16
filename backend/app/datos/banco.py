"""Banco de ejercicios.

Lee el archivo de ``BANCO_EJERCICIOS`` y valida cada ejercicio. El banco real es
privado: vive en ``backend/ejercicios/privado/``, que git ignora, para que los
ejercicios no se publiquen en el repositorio. Si no está configurado, se usa
``ejercicios/banco.json``, que tiene dos ejercicios inventados de ejemplo.

Un error de transcripción (una clave que no existe, un id repetido, un campo
que falta) se detecta al cargar el banco, con un mensaje que dice qué ejercicio
falló, y no en medio de una conversación con un estudiante.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.config import obtener_configuracion
from app.esquemas import Ejercicio


class BancoInvalido(Exception):
    """El archivo del banco no se puede usar. El mensaje dice qué está mal y dónde."""


def leer_banco(ruta: Path) -> list[Ejercicio]:
    """Lee y valida el banco del archivo dado."""
    if not ruta.is_file():
        raise BancoInvalido(f"No existe el archivo del banco: {ruta}")
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BancoInvalido(f"{ruta.name} no es un JSON válido (línea {error.lineno}): {error.msg}") from error
    if not isinstance(crudo, list):
        raise BancoInvalido(f"{ruta.name} debe ser una lista de ejercicios.")

    ejercicios: list[Ejercicio] = []
    vistos: set[str] = set()
    for posicion, dato in enumerate(crudo, start=1):
        nombre = dato.get("id", f"#{posicion}") if isinstance(dato, dict) else f"#{posicion}"
        try:
            ejercicio = Ejercicio.model_validate(dato)
        except ValidationError as error:
            detalle = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'ejercicio'}: {e['msg']}" for e in error.errors())
            raise BancoInvalido(f"El ejercicio {nombre} no es válido: {detalle}") from error
        if ejercicio.id in vistos:
            raise BancoInvalido(f"El id {ejercicio.id} está repetido.")
        vistos.add(ejercicio.id)
        ejercicios.append(ejercicio)
    return ejercicios


@lru_cache
def cargar_banco() -> tuple[Ejercicio, ...]:
    """El banco configurado, leído una sola vez."""
    return tuple(leer_banco(obtener_configuracion().banco_ejercicios))
