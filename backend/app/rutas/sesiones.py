"""Rutas de sesiones de práctica.

Más adelante creará una sesión anónima (sin datos personales) y devolverá su id
para aplicar los límites de mensajes.
"""

from fastapi import APIRouter

from app.esquemas import RespuestaOk, SesionEntrada

router = APIRouter(prefix="/api", tags=["sesiones"])


@router.post("/sesiones", response_model=RespuestaOk)
def crear_sesion(datos: SesionEntrada) -> RespuestaOk:
    """Abre una sesión de práctica (por ahora solo confirma)."""
    return RespuestaOk()
