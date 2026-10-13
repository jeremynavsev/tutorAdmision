"""Ruta de chat con el tutor.

Más adelante: revisa el límite de mensajes, limpia la imagen si viene, arma la
conversación con las instrucciones del tutor, consulta la cadena de proveedores
y verifica con SymPy antes de responder. Por ahora responde un texto fijo.
"""

from fastapi import APIRouter

from app.esquemas import ChatEntrada, ChatSalida

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatSalida)
def conversar(entrada: ChatEntrada) -> ChatSalida:
    """Responde al mensaje del estudiante (modo de prueba)."""
    return ChatSalida(respuesta="Modo de prueba: aquí responderá el tutor.")
