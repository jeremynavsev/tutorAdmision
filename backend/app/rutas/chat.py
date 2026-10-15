"""Ruta de chat con el tutor.

Recibe el mensaje del estudiante (``ChatEntrada``) y devuelve la respuesta del
tutor (``ChatSalida``). Todo el trabajo lo hace ``servicios.tutor``; aquí solo
se traducen sus errores a respuestas HTTP con un mensaje que el frontend le
puede mostrar al estudiante.

Antes de llamar al tutor se revisa el límite diario (``servicios.limites``) y
el mensaje se cuenta solo si el tutor respondió. Lo que queda de cupo va en el
encabezado ``X-Mensajes-Restantes``.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response

from app.esquemas import ChatEntrada, ChatSalida
from app.config import obtener_configuracion
from app.servicios import limites, tutor
from app.servicios.agente import RespuestaInvalida
from app.servicios.imagenes import ImagenInvalida
from app.servicios.modelos_ia import SinProveedores

registro = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

MENSAJE_SIN_SERVICIO = "El tutor no está disponible en este momento. Probá de nuevo en un ratito."
MENSAJE_SESION_INVALIDA = "Tu sesión de práctica se venció. Recargá la página para seguir."


def _ip(peticion: Request) -> str:
    """IP de quien hace el pedido. Detrás de un proxy, la real viene en X-Forwarded-For."""
    if obtener_configuracion().confiar_en_proxy:
        reenviada = peticion.headers.get("x-forwarded-for", "")
        if reenviada.split(",")[0].strip():
            return reenviada.split(",")[0].strip()
    return peticion.client.host if peticion.client else "desconocida"


@router.post(
    "/chat",
    response_model=ChatSalida,
    responses={
        400: {"description": "La foto no se puede usar."},
        401: {"description": "Falta la sesión o no existe."},
        429: {"description": "Se alcanzó el límite de mensajes de hoy."},
        503: {"description": "Ningún proveedor de IA respondió."},
    },
)
def conversar(entrada: ChatEntrada, peticion: Request, respuesta: Response) -> ChatSalida:
    """Responde al mensaje del estudiante, si le queda cupo hoy."""
    ip = _ip(peticion)
    try:
        limites.revisar(entrada.sesion_id, ip)
    except limites.SesionInvalida as error:
        raise HTTPException(status_code=401, detail=MENSAJE_SESION_INVALIDA) from error
    except limites.LimiteAlcanzado as error:
        raise HTTPException(status_code=429, detail=str(error)) from error

    try:
        salida = tutor.responder(entrada)
    except ImagenInvalida as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SinProveedores as error:
        registro.error("Sin proveedores de IA: %s", "; ".join(error.fallos) or "no hay llaves configuradas")
        raise HTTPException(status_code=503, detail=MENSAJE_SIN_SERVICIO) from error
    except RespuestaInvalida as error:
        registro.error("El modelo no devolvió una respuesta utilizable: %s", error)
        raise HTTPException(status_code=503, detail=MENSAJE_SIN_SERVICIO) from error

    # Solo ahora se cuenta el mensaje: si el tutor no respondió, el estudiante no lo pierde.
    assert entrada.sesion_id is not None  # ya lo garantizó limites.revisar
    cupo = limites.registrar(entrada.sesion_id, ip)
    respuesta.headers["X-Mensajes-Restantes"] = str(cupo.restantes)
    return salida
