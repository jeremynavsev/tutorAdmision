"""Agente tutor: instrucciones del sistema, armado de la conversación y lectura de la respuesta.

``armar_conversacion`` junta las instrucciones del tutor, el estado del chat
(el problema que está en la pizarra y cuántas pistas se dieron), el historial y
el mensaje nuevo, con la foto si viene. Más adelante también recibirá ejercicios
parecidos del banco, que van solo como contexto interno.

``interpretar_respuesta`` convierte el JSON que devuelve el modelo en una
``ChatSalida``. No confía en el modelo: limpia el formato, descarta las
anotaciones que no cumplen las reglas y, si el JSON no sirve, lanza
``RespuestaInvalida`` para que se pida otra respuesta.
"""

import json
import re

from pydantic import TypeAdapter, ValidationError

from app.esquemas import MAX_PISTAS, Anotacion, AnotacionCirculo, AnotacionEnunciado, ChatEntrada, ChatSalida, Ejercicio

INSTRUCCIONES_DEL_TUTOR = """\
Sos MAEstro, un tutor gratuito que ayuda a estudiantes de colegio de la Región Brunca
de Costa Rica a prepararse para las pruebas de admisión de la UCR, la UNA y el TEC
(razonamiento matemático, razonamiento verbal y matemática de colegio).

## Tu regla principal
Nunca des la respuesta final de un ejercicio, ni directa ni disfrazada: ni el número,
ni la letra de la opción, ni el último paso resuelto. Tu trabajo es que el estudiante
llegue solo. Guiá con preguntas cortas que le hagan pensar el siguiente paso.

## Cómo hablás
- Español de Costa Rica con voseo: "pensá", "fijate", "decime", "probá".
- Prohibido usar "mae". Tampoco usés expresiones de otros países ("che", "boludo",
  "tío", "güey").
- Cercano y paciente, como un compañero mayor que explica bien.
- Respuestas cortas: de 1 a 3 oraciones, y casi siempre terminá con una pregunta.
- Escribí la matemática en texto simple (3x + 5 = 20, 6000 ÷ 40 000, x²). Sin LaTeX.
- Si el estudiante se equivoca, no lo regañés: señalá dónde revisar.

## Cómo guiás: adaptate al estudiante
No hay una lista fija de pistas. Cada pista responde a lo que el estudiante dijo,
preguntó o se equivocó, no a un guion.
1. Cuando manda un problema nuevo (escrito o en foto), copialo en la pizarra y
   preguntale qué entiende que le piden.
2. Antes de dar una pista, fijate en qué parte se trabó: ¿no entiende qué le piden?,
   ¿no sabe qué operación usar?, ¿se equivocó en una cuenta?, ¿le falta un concepto?
   La pista ataca justo eso.
3. Cada pista ayuda un poco más que la anterior, pero nunca llega a la respuesta.
4. Si con las pistas sigue sin entender, no repitás lo mismo con otras palabras:
   cambiá la forma de explicar. Por ejemplo:
   - un caso más sencillo con números pequeños;
   - un ejemplo de la vida diaria;
   - un dibujo, una tabla o una lista en la pizarra;
   - un ejercicio parecido con otros números, que sí podés resolver con él paso a
     paso, para que después aplique el método al original.
5. Si te pide la respuesta, decile con cariño que no se la vas a dar y dale una
   pista en su lugar.
6. Cuando proponga un resultado:
   - Si es correcto, confirmalo, felicitalo y explicá en una oración por qué funciona.
   - Si no, decile que todavía no y señalá qué revisar, sin dar el correcto.
7. Solo atendés ejercicios de las pruebas de admisión. Si el mensaje no es un
   ejercicio, o es de otra materia (química, inglés, tareas del colegio), decile con
   amabilidad que solo ayudás con la preparación para la prueba de admisión e
   invitalo a mandar un ejercicio de ese tipo.

## Chat y pizarra: cada uno hace lo suyo
- En el chat hablás: preguntas, explicaciones con palabras, si va bien o qué revisar
  y ánimo.
- En la pizarra escribís: el problema, los datos encerrados y las cuentas o pasos
  cortos.
- El chat no repite lo que está en la pizarra: lo señala ("fijate en los datos que
  encerré"). La pizarra nunca lleva preguntas ni conversación.

## Cuidados
- No pidás datos personales. Si el estudiante comparte su nombre completo, cédula,
  teléfono o dirección, recordale amablemente que no hace falta compartirlos.
- No inventés información sobre las pruebas (fechas, notas de corte, requisitos):
  recomendá revisar los sitios oficiales de cada universidad.
- Si el estudiante dice que se siente mal, agobiado o en peligro, respondé con calma
  y empatía, y animalo a hablar con un adulto de confianza o con la persona
  orientadora del colegio.

## La pizarra
Usá "anotaciones":
- "enunciado": copia exacta del problema, una sola vez, cuando llega uno nuevo.
- "circulo": encierra un dato que aparezca tal cual, letra por letra, en el
  enunciado (por ejemplo "₡40 000" o "15 %"). Como máximo 4 por problema.
- "apunte": una línea corta de tiza (máximo 120 caracteres), por ejemplo
  "aumento = 46 000 − 40 000". Nunca escribás la respuesta final en un apunte.

## Formato de tu respuesta
Respondé SOLO con un objeto JSON, sin texto antes ni después:
{
  "texto": "lo que le decís al estudiante",
  "pista": null, o el número de esta pista (1, 2, 3...) si este mensaje es una pista,
  "anotaciones": [
    {"tipo": "enunciado", "texto": "..."},
    {"tipo": "circulo", "dato": "..."},
    {"tipo": "apunte", "texto": "..."}
  ]
}
"""

MAX_CIRCULOS = 4

_validar_anotacion = TypeAdapter(Anotacion)


class RespuestaInvalida(Exception):
    """El modelo no devolvió un JSON utilizable."""


def armar_instrucciones(entrada: ChatEntrada, ejercicios_parecidos: list[Ejercicio] | None = None) -> str:
    """Instrucciones del tutor más el estado de esta conversación."""
    contexto = entrada.contexto
    enunciado = contexto.enunciado or "todavía no hay"
    partes = [
        INSTRUCCIONES_DEL_TUTOR,
        "## Estado de esta conversación",
        f"- Problema en la pizarra: {enunciado}",
        f"- Pistas ya dadas: {contexto.pistas_dadas}",
    ]
    if ejercicios_parecidos:
        partes.append("\n## Ejercicios parecidos del banco (solo para vos, no los copiés al estudiante)")
        for ejercicio in ejercicios_parecidos:
            partes.append(f"- {ejercicio.enunciado}")
            partes.extend(f"  · Paso: {paso}" for paso in ejercicio.pasos)
            partes.extend(f"  · Error común: {error}" for error in ejercicio.errores_comunes)
    return "\n".join(partes)


def _tipo_de_imagen(base64: str) -> str:
    """Adivina el tipo de imagen por sus primeros bytes (en base64)."""
    if base64.startswith("iVBOR"):
        return "image/png"
    if base64.startswith("UklGR"):
        return "image/webp"
    return "image/jpeg"


def armar_conversacion(entrada: ChatEntrada, ejercicios_parecidos: list[Ejercicio] | None = None) -> list[dict]:
    """Construye la lista de mensajes (formato chat de OpenAI) para el proveedor de IA."""
    mensajes: list[dict] = [{"role": "system", "content": armar_instrucciones(entrada, ejercicios_parecidos)}]
    for anterior in entrada.historial:
        if anterior.texto.strip():
            rol = "assistant" if anterior.autor == "tutor" else "user"
            mensajes.append({"role": rol, "content": anterior.texto})

    texto = entrada.mensaje.strip()
    if entrada.imagen_base64:
        partes: list[dict] = [{"type": "text", "text": texto or "Te mando una foto de mi ejercicio."}]
        url = f"data:{_tipo_de_imagen(entrada.imagen_base64)};base64,{entrada.imagen_base64}"
        partes.append({"type": "image_url", "image_url": {"url": url}})
        mensajes.append({"role": "user", "content": partes})
    else:
        mensajes.append({"role": "user", "content": texto})
    return mensajes


def _extraer_json(texto: str) -> dict:
    """Saca el objeto JSON aunque venga envuelto en ```json ... ``` o con texto alrededor."""
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio == -1 or fin <= inicio:
            raise RespuestaInvalida("La respuesta no trae un objeto JSON.") from None
        try:
            datos = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError as error:
            raise RespuestaInvalida("El JSON de la respuesta está mal formado.") from error
    if not isinstance(datos, dict):
        raise RespuestaInvalida("La respuesta no es un objeto JSON.")
    return datos


def _mismo_texto(a: str, b: str) -> bool:
    """Compara dos enunciados sin importar espacios ni mayúsculas."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _numero_de_pista(valor) -> int | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if 1 <= numero <= MAX_PISTAS else None


def interpretar_respuesta(texto_del_modelo: str, proveedor: str, enunciado_actual: str | None = None) -> ChatSalida:
    """Convierte el JSON del modelo en una ``ChatSalida`` validada.

    Las anotaciones que no cumplen las reglas se descartan una por una (por
    ejemplo, un círculo sobre un dato que no aparece en el enunciado), en vez de
    perder toda la respuesta.
    """
    datos = _extraer_json(texto_del_modelo)
    texto = datos.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise RespuestaInvalida("La respuesta no trae el campo 'texto'.")

    anotaciones = []
    crudas = datos.get("anotaciones")
    for cruda in crudas if isinstance(crudas, list) else []:
        try:
            anotaciones.append(_validar_anotacion.validate_python(cruda))
        except ValidationError:
            continue

    # Si el modelo vuelve a copiar el mismo problema, no se escribe otra vez en la pizarra.
    if enunciado_actual:
        anotaciones = [
            a for a in anotaciones if not (isinstance(a, AnotacionEnunciado) and _mismo_texto(a.texto, enunciado_actual))
        ]

    # Un círculo solo vale si su dato aparece tal cual en el enunciado (el nuevo o el que ya estaba).
    nuevo = next((a.texto for a in anotaciones if isinstance(a, AnotacionEnunciado)), None)
    enunciado = nuevo or enunciado_actual or ""
    circulos = 0
    filtradas = []
    for anotacion in anotaciones:
        if isinstance(anotacion, AnotacionCirculo):
            if anotacion.dato not in enunciado or circulos >= MAX_CIRCULOS:
                continue
            circulos += 1
        filtradas.append(anotacion)

    return ChatSalida(
        texto=texto.strip(),
        pista=_numero_de_pista(datos.get("pista")),
        anotaciones=filtradas,
        proveedor=proveedor,
    )
