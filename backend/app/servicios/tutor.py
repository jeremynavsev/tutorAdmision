"""El tutor completo: une la limpieza de fotos, el agente, los proveedores de IA y el verificador.

Pasos de ``responder``:

1. Se ocultan los datos personales del texto (cédulas, teléfonos, correos y
   nombres completos), para que no lleguen al proveedor. Si venían en el
   mensaje, la respuesta empieza avisándole al estudiante.
   Si viene una foto, se limpia (sin metadatos, derecha y reducida).
2. Se arma la conversación y se consulta la cadena de proveedores.
3. Si el modelo devuelve algo que no es el JSON esperado, se le pide de nuevo.
4. Se revisa que la respuesta no regale el resultado. Si lo regala, se le pide
   otra avisándole por qué; si insiste, se manda un mensaje seguro en su lugar.

Errores que puede lanzar: ``ImagenInvalida`` (la foto no sirve),
``SinProveedores`` (ningún proveedor respondió) y ``RespuestaInvalida`` (el
modelo no dio un JSON utilizable ni al segundo intento).
"""

import logging

from app.esquemas import MAX_PISTAS, ChatEntrada, ChatSalida, Ejercicio, Solucion
from app.servicios import modelos_ia
from app.servicios.agente import RespuestaInvalida, armar_conversacion, interpretar_respuesta
from app.servicios.imagenes import limpiar_y_reducir
from app.servicios.privacidad import aviso_de_datos_ocultos, ocultar
from app.servicios.verificador import filtra_la_respuesta

registro = logging.getLogger(__name__)

INTENTOS_POR_FORMATO = 2

AVISO_DE_FILTRACION = (
    "Tu respuesta anterior le daba al estudiante el resultado final, y eso está prohibido. "
    "Respondé de nuevo: una pregunta o una pista que lo acerque, sin escribir el resultado "
    "ni en el texto ni en los apuntes de la pizarra."
)

# Lo que se envía si el modelo insiste en dar el resultado: una respuesta neutra y segura.
RESPUESTA_SEGURA = "Vamos paso a paso para que lo saqués vos. Contame: ¿cuál creés que es el primer paso y por qué?"


def _pedir(mensajes: list[dict], enunciado: str | None) -> ChatSalida:
    """Consulta a los proveedores y lee la respuesta; reintenta si el JSON no sirve."""
    ultimo_error: RespuestaInvalida | None = None
    for _ in range(INTENTOS_POR_FORMATO):
        cruda = modelos_ia.completar(mensajes)
        try:
            return interpretar_respuesta(cruda.texto, cruda.proveedor, enunciado)
        except RespuestaInvalida as error:
            registro.warning("El proveedor %s devolvió un JSON que no sirve: %s", cruda.proveedor, error)
            ultimo_error = error
    raise ultimo_error  # type: ignore[misc]  # el ciclo corre al menos una vez


def _sin_datos_personales(entrada: ChatEntrada) -> tuple[ChatEntrada, list[str]]:
    """Oculta los datos personales del mensaje, del historial y del enunciado.

    Devuelve la entrada limpia y los tipos de datos que traía el mensaje actual.
    """
    mensaje, en_el_mensaje = ocultar(entrada.mensaje)
    historial = [m.model_copy(update={"texto": ocultar(m.texto)[0]}) for m in entrada.historial]
    contexto = entrada.contexto
    if contexto.enunciado:
        contexto = contexto.model_copy(update={"enunciado": ocultar(contexto.enunciado)[0]})
    limpia = entrada.model_copy(update={"mensaje": mensaje, "historial": historial, "contexto": contexto})
    return limpia, en_el_mensaje


def responder(
    entrada: ChatEntrada,
    ejercicios_parecidos: list[Ejercicio] | None = None,
    solucion: Solucion | None = None,
) -> ChatSalida:
    """Devuelve la respuesta del tutor al mensaje del estudiante."""
    entrada, datos_ocultos = _sin_datos_personales(entrada)
    if entrada.imagen_base64:
        entrada = entrada.model_copy(update={"imagen_base64": limpiar_y_reducir(entrada.imagen_base64)})

    enunciado = entrada.contexto.enunciado
    mensajes = armar_conversacion(entrada, ejercicios_parecidos)
    salida = _pedir(mensajes, enunciado)

    if filtra_la_respuesta(salida, entrada, solucion):
        registro.warning("La respuesta de %s revelaba el resultado; se pide otra.", salida.proveedor)
        mensajes_con_aviso = mensajes + [
            {"role": "assistant", "content": salida.texto},
            # Va como "user" y no como "system": no todos los proveedores aceptan un
            # mensaje de sistema a mitad de la conversación.
            {"role": "user", "content": f"[Aviso del sistema, no del estudiante] {AVISO_DE_FILTRACION}"},
        ]
        try:
            salida = _pedir(mensajes_con_aviso, enunciado)
        except (RespuestaInvalida, modelos_ia.SinProveedores):
            salida = ChatSalida(texto=RESPUESTA_SEGURA, proveedor=salida.proveedor)
        if filtra_la_respuesta(salida, entrada, solucion):
            registro.warning("La segunda respuesta de %s también lo revelaba; se envía la respuesta segura.", salida.proveedor)
            salida = ChatSalida(texto=RESPUESTA_SEGURA, proveedor=salida.proveedor)

    # El número de pista no se le confía al modelo: es el contador de la conversación más uno.
    if salida.pista is not None:
        salida = salida.model_copy(update={"pista": min(entrada.contexto.pistas_dadas + 1, MAX_PISTAS)})

    # El aviso lo escribe el código, no la IA: así siempre aparece y siempre dice lo mismo.
    if datos_ocultos:
        salida = salida.model_copy(update={"texto": f"{aviso_de_datos_ocultos(datos_ocultos)} {salida.texto}"})

    return salida
