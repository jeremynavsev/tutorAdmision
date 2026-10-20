"""El tutor completo: une la limpieza de fotos, el agente, los proveedores de IA y el verificador.

Pasos de ``responder``:

1. Se ocultan los datos personales del texto (cédulas, teléfonos, correos y
   nombres completos), para que no lleguen al proveedor. Si venían en el
   mensaje, la respuesta empieza avisándole al estudiante.
   Si viene una foto, se limpia (sin metadatos, derecha y reducida).
2. Se buscan en el banco los ejercicios parecidos al problema: sus pasos y
   errores comunes van en privado en las instrucciones. Si el problema es uno
   del banco, su clave se usa para verificar la respuesta. Si se conoce la
   respuesta y el estudiante propuso una, el código le dice al modelo si es
   correcta, y si no lo es le quita un "¡Correcto!" a la respuesta.
3. Se arma la conversación y se consulta la cadena de proveedores.
4. Si el modelo devuelve algo que no es el JSON esperado, se le pide de nuevo.
5. Se revisa que la respuesta no regale el resultado ni señale una opción con
   sus palabras (``servicios.opciones``). Si lo hace, se le pide otra avisándole
   por qué; si insiste, se manda un mensaje seguro en su lugar.

Errores que puede lanzar: ``ImagenInvalida`` (la foto no sirve),
``SinProveedores`` (ningún proveedor respondió) y ``RespuestaInvalida`` (el
modelo no dio un JSON utilizable ni al segundo intento).
"""

import logging

from app.esquemas import MAX_PISTAS, ChatEntrada, ChatSalida, Ejercicio
from app.servicios import buscador, modelos_ia
from app.servicios.agente import RespuestaInvalida, armar_conversacion, interpretar_respuesta, sin_felicitacion_falsa
from app.servicios.imagenes import limpiar_y_reducir
from app.servicios.privacidad import aviso_de_datos_ocultos, ocultar
from app.servicios.opciones import opcion_senalada
from app.servicios.verificador import filtra_la_respuesta, revisar_propuesta

registro = logging.getLogger(__name__)

INTENTOS_POR_FORMATO = 2

AVISO_DE_FILTRACION = (
    "Tu respuesta anterior le daba al estudiante el resultado final, y eso está prohibido. "
    "Respondé de nuevo: una pregunta o una pista que lo acerque, sin escribir el resultado "
    "ni en el texto ni en los apuntes de la pizarra."
)

# Lo que se envía si el modelo insiste en dar el resultado: una respuesta neutra y segura.
RESPUESTA_SEGURA = "Vamos paso a paso para que lo saqués vos. Contame: ¿cuál creés que es el primer paso y por qué?"

AVISO_DE_OPCION = (
    "Tu respuesta anterior usaba palabras propias de una de las opciones, y así le señalaba al "
    "estudiante cuál elegir. Respondé de nuevo sin usar palabras de las opciones ni describir lo "
    "que dice alguna: pedile que ubique en el texto la frase que responde la pregunta, o que "
    "revise una opción que él elija."
)

# Lo que se envía si el modelo insiste en señalar una opción.
RESPUESTA_SEGURA_OPCIONES = (
    "Vamos por partes: buscá en el texto la frase que responde la pregunta y contámela con tus "
    "palabras. Después revisamos las opciones juntos."
)


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


def _consultar_banco(entrada: ChatEntrada) -> tuple[list[Ejercicio], Ejercicio | None]:
    """Los ejercicios parecidos al problema y, si es uno del banco, ese ejercicio.

    El problema es el de la pizarra; si todavía no hay, el mensaje (ahí suele venir copiado).
    """
    problema = entrada.contexto.enunciado or entrada.mensaje
    indice = buscador.obtener_buscador()
    parecidos = [c.ejercicio for c in indice.buscar(problema)]
    mismo = indice.mismo_ejercicio(problema)
    if parecidos or mismo:
        registro.info("Banco: parecidos %s; mismo ejercicio: %s", [e.id for e in parecidos], mismo.id if mismo else "ninguno")
    if mismo and mismo not in parecidos:
        parecidos = [mismo, *parecidos[: buscador.PARECIDOS_POR_CONSULTA - 1]]
    return parecidos, mismo


def responder(entrada: ChatEntrada) -> ChatSalida:
    """Devuelve la respuesta del tutor al mensaje del estudiante."""
    entrada, datos_ocultos = _sin_datos_personales(entrada)
    if entrada.imagen_base64:
        entrada = entrada.model_copy(update={"imagen_base64": limpiar_y_reducir(entrada.imagen_base64)})

    ejercicios_parecidos, del_banco = _consultar_banco(entrada)
    # Si es un ejercicio del banco, el verificador conoce su clave. En los de matemática
    # también el valor de esa opción; en los verbales, "Solo la 1" nombra una proposición.
    solucion = del_banco.solucion if del_banco else None
    opciones = del_banco.opciones if del_banco and del_banco.area == "Razonamiento matemático" else None
    enunciado = entrada.contexto.enunciado
    # Si se conoce la respuesta, el código juzga lo que propuso el estudiante: el modelo a
    # veces confunde un acierto con un error (o al revés).
    # En el primer mensaje todavía no hay pizarra: si es del banco, se usa su enunciado.
    propuesta = revisar_propuesta(entrada.mensaje, enunciado or (del_banco.enunciado if del_banco else None), solucion, opciones)
    mensajes = armar_conversacion(entrada, ejercicios_parecidos, propuesta)
    salida = _pedir(mensajes, enunciado)

    # Si es del banco, el control de opciones vigila solo la correcta; si no, todas.
    clave = del_banco.solucion.valor if del_banco and del_banco.solucion.tipo == "opcion" else None

    def problema_de(respuesta: ChatSalida) -> tuple[str, str] | None:
        """El aviso para el modelo y la respuesta segura, si la respuesta no se puede enviar."""
        if filtra_la_respuesta(respuesta, entrada, solucion, opciones):
            return AVISO_DE_FILTRACION, RESPUESTA_SEGURA
        if opcion_senalada(
            respuesta,
            entrada,
            del_banco.enunciado if del_banco else None,
            del_banco.opciones if del_banco else None,
            clave,
        ):
            return AVISO_DE_OPCION, RESPUESTA_SEGURA_OPCIONES
        return None

    problema = problema_de(salida)
    if problema:
        aviso, segura = problema
        registro.warning("La respuesta de %s no se puede enviar (%s); se pide otra.", salida.proveedor, aviso[:40])
        mensajes_con_aviso = mensajes + [
            {"role": "assistant", "content": salida.texto},
            # Va como "user" y no como "system": no todos los proveedores aceptan un
            # mensaje de sistema a mitad de la conversación.
            {"role": "user", "content": f"[Aviso del sistema, no del estudiante] {aviso}"},
        ]
        try:
            salida = _pedir(mensajes_con_aviso, enunciado)
        except (RespuestaInvalida, modelos_ia.SinProveedores):
            salida = ChatSalida(texto=segura, proveedor=salida.proveedor)
        segundo = problema_de(salida)
        if segundo:
            registro.warning("La segunda respuesta de %s tampoco se puede enviar; se envía la respuesta segura.", salida.proveedor)
            salida = ChatSalida(texto=segundo[1], proveedor=salida.proveedor)

    if propuesta == "incorrecta":
        salida = salida.model_copy(update={"texto": sin_felicitacion_falsa(salida.texto, "incorrecto")})

    # El número de pista no se le confía al modelo: es el contador de la conversación más uno.
    if salida.pista is not None:
        salida = salida.model_copy(update={"pista": min(entrada.contexto.pistas_dadas + 1, MAX_PISTAS)})

    # El aviso lo escribe el código, no la IA: así siempre aparece y siempre dice lo mismo.
    if datos_ocultos:
        salida = salida.model_copy(update={"texto": f"{aviso_de_datos_ocultos(datos_ocultos)} {salida.texto}"})

    return salida
