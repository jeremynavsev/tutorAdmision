"""Límite de mensajes por sesión.

Cuenta los mensajes de cada sesión (y por día) para que el servicio siga
siendo gratuito y sostenible con las cuotas de los proveedores.
"""


def mensajes_restantes(sesion_id: str) -> int:
    """Cantidad de mensajes que le quedan a la sesión."""
    raise NotImplementedError


def registrar_mensaje(sesion_id: str) -> None:
    """Suma un mensaje al contador de la sesión."""
    raise NotImplementedError


def puede_enviar(sesion_id: str) -> bool:
    """Indica si la sesión todavía puede enviar mensajes."""
    raise NotImplementedError
