"""Pruebas de la detección de datos personales."""

import pytest

from app.esquemas import ChatEntrada
from app.servicios.privacidad import aviso_de_datos_ocultos, encontrar, ocultar
from app.servicios.tutor import responder


def tipos(texto: str) -> list[str]:
    return [h.tipo for h in encontrar(texto)]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("mi cédula es 1-2345-0678", ["cedula"]),
        ("cédula 1 2345 0678", ["cedula"]),
        ("ced: 112340678", ["cedula"]),
        ("mi número de cédula es 503450678", ["cedula"]),
        ("mi DIMEX es 155812345678", ["cedula"]),
        ("mi cel es 8888-8888", ["telefono"]),
        ("llamame al 2771 1234", ["telefono"]),
        ("+506 8765 4321", ["telefono"]),
        ("+50687654321", ["telefono"]),
        ("whatsapp 61234567", ["telefono"]),
        ("mi número es 8888-8888", ["telefono"]),
        ("escribime a ana.rodriguez@gmail.com", ["correo"]),
        ("me llamo Ana Rodríguez", ["nombre"]),
        ("Mi nombre es Ana María Rodríguez Mora", ["nombre"]),
        ("Soy José de la Cruz", ["nombre"]),
    ],
)
def test_detecta_datos_personales(texto, esperado):
    assert tipos(texto) == esperado


@pytest.mark.parametrize(
    "ejercicio",
    [
        "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó?",
        "¿Qué número sigue en la sucesión 2, 6, 12, 20, 30?",
        "cual es el valor de x? 3x-5+20=50",
        "Si 3x + 5 = 20, ¿cuánto vale x?",
        "Un terreno mide 2500 m² y se vende a ₡15 000 000.",
        "Calcule 12345678 + 87654321",
        "La población pasó de 1 250 000 a 1 500 000 habitantes.",
        "En 2024 se vendieron 8000 entradas; en 2025, 6000.",
        "Resolvé 4000-2000 y 8000-4000",
        "Restá 8888-1111 y luego sumá 2500 6000",
        "El código del ejercicio es 2-3456-7",
        "soy de Pérez Zeledón",
        "Soy estudiante del Liceo de San Isidro",
        "me llamo ana",
        "soy Ana",
        "Pie es a zapato como mano es a: A) dedo B) guante C) brazo D) uña",
        "Un tren sale a las 08:30 y recorre 120 km en 1,5 h.",
        "x = 0,15 = 15 %",
    ],
)
def test_no_confunde_un_ejercicio_con_datos_personales(ejercicio):
    assert encontrar(ejercicio) == []


def test_un_numero_largo_sin_contexto_no_cuenta():
    assert encontrar("¿Cuánto es 112340678 dividido entre 3?") == []


def test_oculta_todo_y_deja_el_resto_igual():
    texto, encontrados = ocultar("Soy Ana Rodríguez, cédula 1-2345-0678, mi cel es 8888-8888. ¿Qué practico?")
    assert texto == "Soy [nombre oculto], cédula [cédula oculta], mi cel es [teléfono oculto]. ¿Qué practico?"
    assert encontrados == ["nombre", "cedula", "telefono"]


def test_sin_datos_no_cambia_nada():
    assert ocultar("Si 2x = 14, ¿cuánto vale x?") == ("Si 2x = 14, ¿cuánto vale x?", [])


def test_el_aviso_nombra_lo_que_se_quito():
    assert aviso_de_datos_ocultos(["cedula"]) == (
        "Ojo: quité la cédula de tu mensaje, porque para practicar no hace falta compartir datos personales."
    )
    assert "la cédula, el teléfono y el nombre completo" in aviso_de_datos_ocultos(["cedula", "telefono", "nombre", "cedula"])


# ---------- En el tutor: el dato nunca llega a la IA ----------


def test_el_dato_no_llega_al_modelo_y_el_estudiante_recibe_el_aviso(modelo):
    modelo.responde({"texto": "Mandame un ejercicio para practicar.", "anotaciones": []})
    salida = responder(
        ChatEntrada(
            mensaje="Hola, soy Ana Rodríguez, mi cédula es 1-2345-0678",
            historial=[{"autor": "estudiante", "texto": "mi cel es 8888-8888"}],
        )
    )
    todo_lo_enviado = str(modelo.llamadas[0])
    for dato in ("Ana Rodríguez", "1-2345-0678", "8888-8888"):
        assert dato not in todo_lo_enviado
    assert "[cédula oculta]" in todo_lo_enviado and "[teléfono oculto]" in todo_lo_enviado
    # El aviso nombra los datos en el orden en que aparecían.
    assert salida.texto.startswith("Ojo: quité el nombre completo y la cédula de tu mensaje")
    assert salida.texto.endswith("Mandame un ejercicio para practicar.")


def test_un_dato_que_solo_estaba_en_el_historial_no_repite_el_aviso(modelo):
    modelo.responde({"texto": "¿Qué te piden?", "anotaciones": []})
    salida = responder(ChatEntrada(mensaje="dame una pista", historial=[{"autor": "estudiante", "texto": "mi cel es 8888-8888"}]))
    assert salida.texto == "¿Qué te piden?"
    assert "8888-8888" not in str(modelo.llamadas[0])


def test_un_ejercicio_llega_intacto(modelo):
    modelo.responde({"texto": "¿Qué te piden?", "anotaciones": []})
    ejercicio = "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó?"
    assert responder(ChatEntrada(mensaje=ejercicio)).texto == "¿Qué te piden?"
    assert modelo.llamadas[0][-1]["content"] == ejercicio
