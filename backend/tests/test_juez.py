"""Pruebas del juez con IA de la evaluación (con un modelo simulado)."""

import json

from evaluacion import juez
from evaluacion.generar_casos import referencia
from app.esquemas import Ejercicio

TURNOS = [("3x + 5 = 20", "¿Qué te piden encontrar?"), ("no entendí", "Restá 5: 3x = 15, entonces ¿cuánto es 3x?")]


def respuesta_del_juez(*calificaciones) -> str:
    return json.dumps({"respuestas": [{"n": i, **c} for i, c in enumerate(calificaciones, start=1)]})


def test_la_consulta_numera_las_respuestas_y_trae_la_referencia():
    mensajes = juez.armar_consulta(TURNOS, "Respuesta correcta: x = 5")
    usuario = mensajes[1]["content"]
    assert mensajes[0]["content"] == juez.INSTRUCCIONES_DEL_JUEZ
    assert "Respuesta correcta: x = 5" in usuario
    assert "Tutor (respuesta 1)" in usuario and "Tutor (respuesta 2)" in usuario


def test_sin_referencia_no_menciona_datos_del_ejercicio():
    assert "Datos del ejercicio" not in juez.armar_consulta(TURNOS, None)[1]["content"]


def test_convierte_cada_criterio_en_una_revision():
    texto = respuesta_del_juez(
        {"revela": False, "se_contesta": False, "contenido_correcto": True, "valora_bien": None, "se_entiende": True},
        {"revela": False, "se_contesta": True, "contenido_correcto": True, "valora_bien": None, "se_entiende": True,
         "comentario": "Escribe 3x = 15 y luego lo pregunta."},
    )
    primera, segunda = juez.interpretar(texto, 2)
    assert all(c.paso for c in primera) and len(primera) == 4  # valora_bien = null no cuenta
    fallas = [c for c in segunda if not c.paso]
    assert [c.nombre for c in fallas] == ["juez: no se contesta sola"]
    assert fallas[0].detalle == "Escribe 3x = 15 y luego lo pregunta."


def test_si_falta_una_respuesta_no_inventa_calificaciones():
    texto = respuesta_del_juez({"revela": True, "comentario": "Dice x = 5."})
    primera, segunda = juez.interpretar(texto, 2)
    assert [(c.nombre, c.paso) for c in primera] == [("juez: no revela", False)]
    assert segunda == []


def test_si_el_juez_falla_la_evaluacion_sigue(monkeypatch):
    class Cruda:
        texto = "esto no es JSON"

    monkeypatch.setattr(juez.modelos_ia, "completar", lambda *a, **k: Cruda())
    assert juez.juzgar(TURNOS, None, []) == [[], []]


def test_usa_los_proveedores_del_juez(monkeypatch):
    usados = {}

    class Cruda:
        texto = respuesta_del_juez({}, {})

    def completar(mensajes, **kw):
        usados.update(kw)
        return Cruda()

    monkeypatch.setattr(juez.modelos_ia, "completar", completar)
    juez.juzgar(TURNOS, None, ["juez-falso"])
    assert usados["proveedores"] == ["juez-falso"]


def test_la_referencia_trae_la_clave_y_los_pasos():
    e = Ejercicio(id="x", tema="t", area="Razonamiento matemático", enunciado="¿?", opciones=["9", "10"],
                  solucion={"tipo": "opcion", "valor": "B"}, pasos=["Sumar horas.", "Dividir entre 3."], errores_comunes=[])
    assert referencia(e) == "Respuesta correcta: B) 10\nCómo se resuelve: Sumar horas. Dividir entre 3."
