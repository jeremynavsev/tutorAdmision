"""Cadena de proveedores de IA: Gemini → Groq → Mistral.

Usa el cliente ``openai`` contra los endpoints compatibles de cada proveedor.
Si uno falla (error, tiempo agotado o cuota), pasa al siguiente. Solo se usan
proveedores con llave configurada. Devuelve el texto y el nombre del proveedor
que respondió.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Proveedor:
    """Datos de conexión de un proveedor compatible con la API de OpenAI."""

    nombre: str
    url_base: str
    modelo: str
    llave: str


def proveedores_disponibles() -> list[Proveedor]:
    """Lista los proveedores con llave configurada, en orden de prioridad."""
    raise NotImplementedError


def completar(mensajes: list[dict[str, str]]) -> tuple[str, str]:
    """Pide una respuesta a la cadena de proveedores.

    Devuelve ``(texto, nombre_del_proveedor)``.
    """
    raise NotImplementedError
