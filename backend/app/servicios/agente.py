"""Agente tutor: instrucciones del sistema y armado de la conversación.

Define la personalidad de MAEstro (cercano, con voseo, paciente) y su regla
principal: guiar con preguntas y hasta tres pistas graduales, nunca dar la
respuesta final. Arma los mensajes que se envían al proveedor de IA a partir
de la ``ChatEntrada`` (mensaje, foto, historial y contexto) y, más adelante, de
los ejercicios parecidos del banco, que van solo como contexto interno.

El modelo debe responder en JSON con la forma de ``ChatSalida``: el texto, el
número de pista si es una pista y las anotaciones para la pizarra.
"""

from app.esquemas import ChatEntrada, ChatSalida, Ejercicio

INSTRUCCIONES_DEL_TUTOR = """\
(Pendiente) Instrucciones del sistema para el tutor MAEstro.
"""


def armar_instrucciones(ejercicios_parecidos: list[Ejercicio]) -> str:
    """Texto de sistema, con los pasos y errores comunes de ejercicios parecidos del banco."""
    raise NotImplementedError


def armar_conversacion(entrada: ChatEntrada, ejercicios_parecidos: list[Ejercicio]) -> list[dict]:
    """Construye la lista de mensajes (formato chat) para el proveedor de IA."""
    raise NotImplementedError


def interpretar_respuesta(texto_del_modelo: str, proveedor: str) -> ChatSalida:
    """Convierte el JSON que devolvió el modelo en una ``ChatSalida`` validada."""
    raise NotImplementedError
