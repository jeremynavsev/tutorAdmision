"""Agente tutor: instrucciones del sistema y armado de la conversación.

Define la personalidad de MAEstro (cercano, con voseo, paciente) y su regla
principal: guiar con preguntas y pistas graduales, nunca dar la respuesta final.
También arma la lista de mensajes que se envía al proveedor de IA, combinando
las instrucciones, el ejercicio activo (con su solución y errores comunes solo
como contexto interno) y el historial de la sesión.
"""

from app.esquemas import Ejercicio, MensajeChat

INSTRUCCIONES_DEL_TUTOR = """\
(Pendiente) Instrucciones del sistema para el tutor MAEstro.
"""


def armar_instrucciones(ejercicio: Ejercicio | None) -> str:
    """Devuelve el texto de sistema para el ejercicio activo."""
    raise NotImplementedError


def armar_conversacion(
    ejercicio: Ejercicio | None,
    historial: list[MensajeChat],
    mensaje_nuevo: str,
) -> list[dict[str, str]]:
    """Construye la lista de mensajes (formato chat) para el proveedor de IA."""
    raise NotImplementedError


def es_pista(respuesta: str) -> bool:
    """Indica si una respuesta del tutor debe mostrarse como pista."""
    raise NotImplementedError
