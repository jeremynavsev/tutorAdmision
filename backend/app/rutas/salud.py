"""Ruta de salud: permite saber si el backend está en línea."""

from fastapi import APIRouter

from app.esquemas import RespuestaOk

router = APIRouter(prefix="/api", tags=["salud"])


@router.get("/salud", response_model=RespuestaOk)
def salud() -> RespuestaOk:
    """Devuelve ``{"ok": true}`` si la API responde."""
    return RespuestaOk()
