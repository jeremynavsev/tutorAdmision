"""Evaluador con IA ("juez") de las conversaciones de prueba.

Las revisiones por patrones de ``evaluar.py`` ven lo evidente (si dijo "¡Exacto!",
si apareció la letra de la clave, si tuteó), pero no si una pista es correcta o
si el tutor se contestó su propia pregunta. Para eso, un segundo modelo lee la
conversación completa y califica cada respuesta del tutor.

Se hace una sola consulta por conversación, para gastar poca cuota, y conviene
usar un proveedor distinto al del tutor (``--juez gemini``), para no gastar la
cuota que usa el tutor y para que el modelo no se califique a sí mismo.

Si el caso trae una ``referencia`` (la clave y los pasos de un ejercicio del
banco), el juez la usa para saber cuál es la respuesta correcta.
"""

import json
import logging
from dataclasses import dataclass

from app.servicios import modelos_ia
from app.servicios.agente import RespuestaInvalida, _extraer_json
from app.servicios.modelos_ia import Proveedor

registro = logging.getLogger(__name__)

INSTRUCCIONES_DEL_JUEZ = """\
Sos un evaluador de un tutor de IA para estudiantes de colegio que se preparan para la
Prueba de Aptitud Académica de la UCR y la UNA. El tutor debe guiar con preguntas y
pistas, explicar cuando el estudiante se traba, y nunca dar la respuesta final.

Vas a leer una conversación entre un estudiante y el tutor. Calificá cada respuesta del
tutor, numeradas desde 1, con estos criterios:

- "revela": true si la respuesta da la respuesta final del ejercicio, directa o
  disfrazada: la letra correcta, su valor, o el último paso ya resuelto. Si el
  estudiante ya había dicho la respuesta correcta, confirmarla NO es revelar.
- "se_contesta": true si el tutor escribe el resultado de un paso y en la misma
  respuesta le pregunta al estudiante ese mismo resultado.
- "contenido_correcto": false si dice algo falso: una cuenta mal hecha, una pista
  que lleva a una respuesta incorrecta, o una regla mal explicada.
- "valora_bien": si el último mensaje del estudiante proponía algo (una respuesta,
  un paso, una operación), true si el tutor dijo correctamente si estaba bien o mal;
  false si felicitó algo incorrecto o rechazó algo correcto. null si el estudiante no
  propuso nada ("no entendí", "dame una pista", el enunciado solo).
- "se_entiende": false si un estudiante de colegio difícilmente entendería la
  respuesta (muy abstracta, enredada o con varias preguntas a la vez).
- "explica_el_porque": si el estudiante pidió ayuda o dijo que no sabe o no entiende,
  true si la respuesta da la idea de lo que conviene hacer (el porqué), y no solo una orden
  ("calculá X") o una pregunta. null si el estudiante no pidió ayuda.
- "repite_pregunta": true si la respuesta repite, con otras palabras, una pregunta que el
  tutor ya había hecho y que el estudiante no supo responder, en vez de explicar.
- "comentario": una oración que explique cualquier problema; vacía si no hay.

Sé estricto con "revela", "se_contesta" y "contenido_correcto": son los errores más
graves. Si no estás seguro de que algo esté mal, no lo marqués.

Respondé SOLO con un objeto JSON:
{"respuestas": [{"n": 1, "revela": false, "se_contesta": false, "contenido_correcto": true,
"valora_bien": null, "se_entiende": true, "explica_el_porque": null, "repite_pregunta": false,
"comentario": ""}, …]}
"""

# Qué criterio pasa con qué valor. None (no aplica) no genera revisión.
CRITERIOS = {
    "revela": ("juez: no revela", False),
    "se_contesta": ("juez: no se contesta sola", False),
    "contenido_correcto": ("juez: contenido correcto", True),
    "valora_bien": ("juez: valora bien la propuesta", True),
    "se_entiende": ("juez: se entiende", True),
    "explica_el_porque": ("juez: explica el porqué", True),
    "repite_pregunta": ("juez: no repite la pregunta", False),
}


@dataclass
class Calificacion:
    nombre: str
    paso: bool
    detalle: str = ""


def armar_consulta(turnos: list[tuple[str, str]], referencia: str | None) -> list[dict]:
    """Los mensajes para el juez: la conversación completa con las respuestas del tutor numeradas."""
    lineas = []
    if referencia:
        lineas += ["Datos del ejercicio (el estudiante no los ve):", referencia, ""]
    lineas.append("Conversación:")
    for n, (estudiante, tutor) in enumerate(turnos, start=1):
        lineas += [f"Estudiante: {estudiante}", f"Tutor (respuesta {n}): {tutor}", ""]
    return [
        {"role": "system", "content": INSTRUCCIONES_DEL_JUEZ},
        {"role": "user", "content": "\n".join(lineas)},
    ]


def interpretar(texto: str, cantidad: int) -> list[list[Calificacion]]:
    """Convierte el JSON del juez en calificaciones por respuesta del tutor."""
    datos = _extraer_json(texto)
    respuestas = datos.get("respuestas")
    if not isinstance(respuestas, list):
        raise RespuestaInvalida("El juez no devolvió la lista de respuestas.")
    por_numero = {r.get("n"): r for r in respuestas if isinstance(r, dict)}
    resultado: list[list[Calificacion]] = []
    for n in range(1, cantidad + 1):
        r = por_numero.get(n, {})
        comentario = str(r.get("comentario") or "").strip()
        calificaciones = []
        for clave, (nombre, bueno) in CRITERIOS.items():
            valor = r.get(clave)
            if isinstance(valor, bool):
                paso = valor == bueno
                calificaciones.append(Calificacion(nombre, paso, "" if paso else comentario))
        resultado.append(calificaciones)
    return resultado


def juzgar(turnos: list[tuple[str, str]], referencia: str | None, proveedores: list[Proveedor]) -> list[list[Calificacion]]:
    """Califica cada respuesta del tutor. Si el juez falla, devuelve listas vacías (no bloquea la evaluación)."""
    try:
        cruda = modelos_ia.completar(armar_consulta(turnos, referencia), proveedores=proveedores)
        return interpretar(cruda.texto, len(turnos))
    except (RespuestaInvalida, modelos_ia.SinProveedores, json.JSONDecodeError) as error:
        registro.warning("El juez no pudo calificar esta conversación: %s", error)
        return [[] for _ in turnos]
