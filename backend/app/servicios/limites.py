"""Límite de mensajes por día, por estudiante y por conexión.

Para que el servicio siga siendo gratuito y alcance la cuota de los proveedores:

- cada sesión (un estudiante) puede mandar ``LIMITE_MENSAJES_SESION`` por día;
- cada conexión, ``LIMITE_MENSAJES_CONEXION`` por día. Es alto a propósito,
  porque en un colegio todo un laboratorio sale por la misma conexión; solo
  evita que alguien se salte el límite de su sesión borrando el navegador.

El día se cuenta en hora de Costa Rica. Primero se revisa si queda cupo y el
mensaje se cuenta solo cuando el tutor respondió: si un proveedor falla, el
estudiante no pierde ese mensaje.

Privacidad: de la conexión no se guarda la IP sino una huella, un resumen
irreversible hecho con una clave secreta y la fecha. Con la huella se puede
contar, pero no se puede recuperar la IP ni reconocer la conexión otro día.
"""

import datetime
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from functools import lru_cache

from app.config import obtener_configuracion
from app.datos.db import Sesion, Uso, sesion_bd

registro = logging.getLogger(__name__)

# Costa Rica está en UTC−6 todo el año (no tiene horario de verano).
HORA_DE_COSTA_RICA = datetime.timezone(datetime.timedelta(hours=-6), "America/Costa_Rica")

MENSAJE_LIMITE_SESION = "Llegaste al límite de mensajes de hoy. Mañana podés seguir practicando."
MENSAJE_LIMITE_CONEXION = (
    "Se alcanzó el límite de mensajes de hoy desde esta conexión. Mañana se puede seguir practicando."
)


class LimiteAlcanzado(Exception):
    """No quedan mensajes por hoy. El mensaje está pensado para mostrárselo al estudiante."""


class SesionInvalida(Exception):
    """El mensaje no trae una sesión válida (falta o no existe)."""


@dataclass(frozen=True)
class Cupo:
    """Cuántos mensajes le quedan hoy a la sesión."""

    restantes: int


def hoy(ahora: datetime.datetime | None = None) -> datetime.date:
    """La fecha de hoy en Costa Rica."""
    return (ahora or datetime.datetime.now(datetime.UTC)).astimezone(HORA_DE_COSTA_RICA).date()


@lru_cache
def _secreto() -> bytes:
    configurado = obtener_configuracion().secreto_huellas
    if configurado:
        return configurado.encode()
    registro.warning(
        "SECRETO_HUELLAS no está configurado: se usa uno al azar, así que los contadores por conexión "
        "vuelven a cero cada vez que se reinicia el servidor."
    )
    return secrets.token_bytes(32)


def huella_de_conexion(ip: str, dia: datetime.date) -> str:
    """Resumen irreversible de la IP para ese día. Cambia de un día a otro."""
    mensaje = f"{dia.isoformat()}|{ip}".encode()
    return hmac.new(_secreto(), mensaje, hashlib.sha256).hexdigest()[:32]


def _clave_sesion(sesion_id: str) -> str:
    return f"sesion:{sesion_id}"


def _clave_conexion(ip: str, dia: datetime.date) -> str:
    return f"origen:{huella_de_conexion(ip, dia)}"


def revisar(sesion_id: str | None, ip: str, ahora: datetime.datetime | None = None) -> Cupo:
    """Revisa que la sesión exista y que le quede cupo hoy. No cuenta nada todavía.

    Lanza ``SesionInvalida`` o ``LimiteAlcanzado``.
    """
    if not sesion_id:
        raise SesionInvalida("Falta la sesión.")
    config = obtener_configuracion()
    dia = hoy(ahora)
    with sesion_bd() as bd:
        if bd.get(Sesion, sesion_id) is None:
            raise SesionInvalida("La sesión no existe.")
        de_la_sesion = bd.get(Uso, (_clave_sesion(sesion_id), dia))
        de_la_conexion = bd.get(Uso, (_clave_conexion(ip, dia), dia))
        usados_sesion = de_la_sesion.mensajes if de_la_sesion else 0
        usados_conexion = de_la_conexion.mensajes if de_la_conexion else 0
    if usados_sesion >= config.limite_mensajes_sesion:
        raise LimiteAlcanzado(MENSAJE_LIMITE_SESION)
    if usados_conexion >= config.limite_mensajes_conexion:
        raise LimiteAlcanzado(MENSAJE_LIMITE_CONEXION)
    return Cupo(restantes=config.limite_mensajes_sesion - usados_sesion)


def registrar(sesion_id: str, ip: str, ahora: datetime.datetime | None = None) -> Cupo:
    """Cuenta un mensaje para la sesión y para la conexión. Se llama cuando el tutor ya respondió."""
    dia = hoy(ahora)
    with sesion_bd() as bd:
        for clave in (_clave_sesion(sesion_id), _clave_conexion(ip, dia)):
            uso = bd.get(Uso, (clave, dia))
            if uso is None:
                bd.add(Uso(clave=clave, dia=dia, mensajes=1))
            else:
                uso.mensajes += 1
        bd.flush()
        usados = bd.get(Uso, (_clave_sesion(sesion_id), dia)).mensajes
    return Cupo(restantes=max(0, obtener_configuracion().limite_mensajes_sesion - usados))
