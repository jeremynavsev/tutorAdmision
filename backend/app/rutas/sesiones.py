"""Rutas de sesiones de práctica.

Una sesión es un identificador al azar que se crea cuando el estudiante acepta
el aviso de entrada. No guarda ningún dato personal: solo sirve para contar
cuántos mensajes manda por día y aplicar el límite.
"""

import uuid

from fastapi import APIRouter, HTTPException

from app.datos.db import Sesion, sesion_bd
from app.esquemas import SesionEntrada, SesionSalida

router = APIRouter(prefix="/api", tags=["sesiones"])


@router.post(
    "/sesiones",
    response_model=SesionSalida,
    status_code=201,
    responses={400: {"description": "No se aceptó el aviso de entrada."}},
)
def crear_sesion(datos: SesionEntrada) -> SesionSalida:
    """Crea una sesión anónima. Solo si el estudiante aceptó el aviso de entrada."""
    if not datos.acepto_aviso:
        raise HTTPException(status_code=400, detail="Para practicar hay que aceptar el aviso de entrada.")
    sesion_id = str(uuid.uuid4())
    with sesion_bd() as bd:
        bd.add(Sesion(id=sesion_id))
    return SesionSalida(sesion_id=sesion_id)
