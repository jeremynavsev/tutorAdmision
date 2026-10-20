"""Pruebas del control de que el tutor no señale una opción con sus palabras."""

import pytest

from app.esquemas import ChatEntrada, ChatSalida, Ejercicio
from app.servicios import buscador
from app.servicios.buscador import Buscador
from app.servicios.opciones import opcion_senalada, palabras_propias, separar
from app.servicios.tutor import AVISO_DE_OPCION, RESPUESTA_SEGURA_OPCIONES, responder

LECTOR = "El buen lector no es el que lee muchos libros, sino el que sabe qué busca en cada uno.\n¿Qué característica tiene el buen lector?"
OPCIONES = ["Lee muy rápido.", "Tiene muchos libros.", "Lee con un propósito.", "Memoriza lo que lee."]
PEGADO = LECTOR + "\n" + "\n".join(f"{l}) {o}" for l, o in zip("ABCD", OPCIONES))


def entrada(mensaje="no entendí", historial=(), enunciado=LECTOR) -> ChatEntrada:
    return ChatEntrada(mensaje=mensaje, historial=list(historial), contexto={"enunciado": enunciado})


def salida(texto: str) -> ChatSalida:
    return ChatSalida(texto=texto)


def test_separa_el_texto_de_las_opciones():
    texto, opciones = separar(PEGADO)
    assert texto.strip() == LECTOR and opciones == OPCIONES
    assert separar("Sin opciones, ¿cuánto es 2 + 2?") == ("Sin opciones, ¿cuánto es 2 + 2?", [])


def test_las_palabras_propias_no_estan_en_el_texto_ni_en_otra_opcion():
    propias = palabras_propias(LECTOR, OPCIONES)
    assert propias[2] == {"proposi"}  # "lee" está en el texto; "propósito" solo en la C
    assert "libr" not in propias[1]  # "libros" está en el texto


# ---------- Ejercicio del banco: se vigila la clave ----------


def test_en_el_banco_bloquea_las_palabras_de_la_opcion_correcta():
    assert opcion_senalada(salida("¿Con cuál opción relacionás la palabra «propósito»?"), entrada(), LECTOR, OPCIONES, "C") == "C"


def test_en_el_banco_puede_descartar_una_opcion_incorrecta():
    descarte = salida("Fijate en la D: habla de memorizar. ¿El texto dice algo de eso?")
    assert opcion_senalada(descarte, entrada(), LECTOR, OPCIONES, "C") is None


def test_puede_usar_las_palabras_del_texto():
    pista = salida("Buscá la frase que sigue a «sino el que». ¿Qué dice sobre lo que busca el lector?")
    assert opcion_senalada(pista, entrada(), LECTOR, OPCIONES, "C") is None


def test_si_el_estudiante_ya_menciono_la_opcion_puede_hablar_de_ella():
    confirma = salida("¡Eso! Leer con un propósito es saber qué se busca.")
    assert opcion_senalada(confirma, entrada("¿es la C?"), LECTOR, OPCIONES, "C") is None
    assert opcion_senalada(confirma, entrada("creo que lee con propósito"), LECTOR, OPCIONES, "C") is None


def test_pegar_el_problema_no_cuenta_como_mencionar_la_opcion():
    pista = salida("¿Cuál opción habla de propósito?")
    assert opcion_senalada(pista, entrada(PEGADO, enunciado=None), LECTOR, OPCIONES, "C") == "C"


def test_tambien_revisa_la_pizarra():
    con_apunte = ChatSalida(texto="Mirá la pizarra.", anotaciones=[{"tipo": "apunte", "texto": "clave: propósito"}])
    assert opcion_senalada(con_apunte, entrada(), LECTOR, OPCIONES, "C") == "C"


# ---------- Ejercicio fuera del banco: se vigilan todas las opciones ----------


def test_fuera_del_banco_vigila_todas_las_opciones():
    con_opciones_en_pizarra = entrada(enunciado=PEGADO)
    assert opcion_senalada(salida("¿Cuál habla de propósito?"), con_opciones_en_pizarra) == "C"
    assert opcion_senalada(salida("¿Alguna habla de memorizar?"), con_opciones_en_pizarra) == "D"
    assert opcion_senalada(salida("Ubicá la frase después de «sino». ¿Qué dice?"), con_opciones_en_pizarra) is None


def test_fuera_del_banco_toma_las_opciones_del_problema_pegado():
    historial = [{"autor": "estudiante", "texto": PEGADO}, {"autor": "tutor", "texto": "¿Qué dice el texto?"}]
    assert opcion_senalada(salida("¿Cuál habla de propósito?"), entrada("no sé", historial, enunciado=None)) == "C"


def test_sin_opciones_no_hay_nada_que_vigilar():
    assert opcion_senalada(salida("Restá 5 a ambos lados."), entrada(enunciado="Si 3x + 5 = 20, ¿cuánto vale x?")) is None


# ---------- En el tutor ----------


@pytest.fixture
def banco_lector(monkeypatch):
    ejercicio = Ejercicio(
        id="lector", tema="Lectura", area="Razonamiento verbal", enunciado=LECTOR, opciones=OPCIONES,
        solucion={"tipo": "opcion", "valor": "C"}, pasos=["Ubicar la frase clave."], errores_comunes=[],
    )
    monkeypatch.setattr(buscador, "obtener_buscador", lambda: Buscador([ejercicio]))


def test_el_tutor_pide_otra_respuesta_si_senala_la_opcion(modelo, banco_lector):
    modelo.responde(
        {"texto": "¿Con cuál opción relacionás la palabra «propósito»?", "anotaciones": []},
        {"texto": "Buscá la frase que sigue a «sino el que». ¿Qué dice?", "anotaciones": []},
    )
    respuesta = responder(entrada("no entendí", [{"autor": "estudiante", "texto": PEGADO}]))
    assert respuesta.texto == "Buscá la frase que sigue a «sino el que». ¿Qué dice?"
    assert AVISO_DE_OPCION in modelo.llamadas[1][-1]["content"]


def test_si_insiste_se_envia_la_respuesta_segura_de_lectura(modelo, banco_lector):
    senala = {"texto": "¿Cuál opción habla de un propósito?", "anotaciones": []}
    modelo.responde(senala, senala)
    respuesta = responder(entrada("no entendí", [{"autor": "estudiante", "texto": PEGADO}]))
    assert respuesta.texto == RESPUESTA_SEGURA_OPCIONES
