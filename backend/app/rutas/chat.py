"""Ruta de chat con el tutor.

Recibe el mensaje del estudiante (``ChatEntrada``) y devuelve la respuesta del
tutor (``ChatSalida``). Todo el trabajo lo hace ``servicios.tutor``; aquí solo
se traducen sus errores a respuestas HTTP con un mensaje que el frontend le
puede mostrar al estudiante.

Pendiente (fase 3): límite de mensajes por sesión.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.esquemas import ChatEntrada, ChatSalida
from app.servicios import tutor
from app.servicios.agente import RespuestaInvalida
from app.servicios.imagenes import ImagenInvalida
from app.servicios.modelos_ia import SinProveedores

registro = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

MENSAJE_SIN_SERVICIO = "El tutor no está disponible en este momento. Probá de nuevo en un ratito."


@router.post(
    "/chat",
    response_model=ChatSalida,
    responses={
        400: {"description": "La foto no se puede usar."},
        503: {"description": "Ningún proveedor de IA respondió."},
    },
)
def conversar(entrada: ChatEntrada) -> ChatSalida:
    """Responde al mensaje del estudiante."""
    try:
        return tutor.responder(entrada)
    except ImagenInvalida as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SinProveedores as error:
        registro.error("Sin proveedores de IA: %s", "; ".join(error.fallos) or "no hay llaves configuradas")
        raise HTTPException(status_code=503, detail=MENSAJE_SIN_SERVICIO) from error
    except RespuestaInvalida as error:
        registro.error("El modelo no devolvió una respuesta utilizable: %s", error)
        raise HTTPException(status_code=503, detail=MENSAJE_SIN_SERVICIO) from error
