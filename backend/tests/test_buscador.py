"""Pruebas de la búsqueda de ejercicios parecidos y de su uso en el tutor."""

import json

import pytest

from app.datos.banco import BancoInvalido
from app.esquemas import ChatEntrada, Ejercicio
from app.servicios import buscador
from app.servicios.buscador import Buscador, palabras

# La función real: las pruebas reemplazan buscador.obtener_buscador por el banco de ejemplo.
OBTENER_BUSCADOR = buscador.obtener_buscador
from app.servicios.tutor import responder


def ejercicio(id: str, enunciado: str, tema: str = "Prueba", clave: str = "A", opciones=("1", "2", "3", "4")) -> Ejercicio:
    return Ejercicio(
        id=id,
        tema=tema,
        area="Razonamiento matemático",
        enunciado=enunciado,
        opciones=list(opciones),
        solucion={"tipo": "opcion", "valor": clave},
        pasos=[f"Paso de {id}."],
        errores_comunes=[f"Error de {id}."],
    )


BILLETERA = ejercicio(
    "mitades",
    "Carlos tenía 800 colones en la billetera. Le regaló la mitad de lo que tenía a cada sobrino que llegó. "
    "¿Cuánto le dio al cuarto sobrino?",
    tema="Mitades sucesivas",
)
CALENDARIO = ejercicio(
    "calendario",
    "Las entregas se hacen cada 150 días y la primera es un miércoles. ¿Qué día de la semana es la tercera entrega?",
    tema="Calendario",
)
LECTURA = ejercicio(
    "lectura",
    "Dicen que la historia se repite, pero sus lecciones no se aprovechan. ¿Cuál es una idea implícita en el texto?",
    tema="Idea implícita",
)
BANCO = Buscador([BILLETERA, CALENDARIO, LECTURA])


def test_las_palabras_no_dependen_de_tildes_mayusculas_ni_miles():
    assert palabras("¿Qué DÍA de la semana?") == ["dia", "semana"]
    assert palabras("₡3 000 y 3.000") == ["3000", "3000"]
    assert "niño" in palabras("El niño")


def test_encuentra_el_ejercicio_mas_parecido():
    resultado = BANCO.buscar("Si hoy es miércoles, ¿qué día de la semana será dentro de 150 días?")
    assert resultado[0].ejercicio.id == "calendario"


def test_no_devuelve_ejercicios_que_no_se_parecen():
    assert BANCO.buscar("hola, no entiendo") == []
    assert BANCO.buscar("") == []


def test_reconoce_el_mismo_ejercicio_copiado_con_otro_formato():
    copiado = BILLETERA.enunciado.upper().replace("¿", "").replace("800", "800 ")
    assert BANCO.mismo_ejercicio(copiado) == BILLETERA


def test_con_otros_numeros_no_es_el_mismo_ejercicio():
    otro = BILLETERA.enunciado.replace("800", "1600")
    assert BANCO.buscar(otro)[0].ejercicio == BILLETERA  # se parece…
    assert BANCO.mismo_ejercicio(otro) is None  # …pero su clave no sirve


def test_un_pedazo_del_ejercicio_no_es_el_mismo():
    assert BANCO.mismo_ejercicio("Carlos tenía 800 colones en la billetera.") is None


def test_un_banco_vacio_no_encuentra_nada():
    vacio = Buscador([])
    assert vacio.buscar("cualquier cosa") == [] and vacio.mismo_ejercicio("cualquier cosa") is None


def test_si_el_banco_no_se_puede_leer_el_tutor_sigue(monkeypatch):
    def roto():
        raise BancoInvalido("banco.json no es un JSON válido")

    monkeypatch.setattr(buscador, "cargar_banco", roto)
    assert OBTENER_BUSCADOR.__wrapped__().ejercicios == []  # sin la caché, para no guardar el banco vacío


# ---------- En el tutor ----------


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setattr(buscador, "obtener_buscador", lambda: BANCO)


def instrucciones(modelo) -> str:
    return modelo.llamadas[0][0]["content"]


def test_los_parecidos_llegan_al_tutor_en_privado(modelo, banco):
    modelo.responde({"texto": "¿Cuántos días tiene una semana?", "anotaciones": []})
    responder(ChatEntrada(mensaje="ayuda", contexto={"enunciado": "Hoy es lunes. ¿Qué día de la semana será en 150 días?"}))
    sistema = instrucciones(modelo)
    assert "Paso de calendario." in sistema and "Error de calendario." in sistema
    assert "Paso de mitades." not in sistema


def test_sin_pizarra_busca_con_el_mensaje(modelo, banco):
    modelo.responde({"texto": "¿Qué te piden?", "anotaciones": []})
    responder(ChatEntrada(mensaje=f"Ayudame con este: {LECTURA.enunciado}"))
    assert "Paso de lectura." in instrucciones(modelo)


def test_un_saludo_no_trae_ejercicios(modelo, banco):
    modelo.responde({"texto": "¡Hola! ¿Qué ejercicio querés practicar?", "anotaciones": []})
    responder(ChatEntrada(mensaje="hola"))
    assert "Ejercicios parecidos" not in instrucciones(modelo)


def test_si_es_del_banco_la_clave_bloquea_la_letra(modelo, banco):
    modelo.responde(
        {"texto": "Es la A.", "anotaciones": []},
        {"texto": "¿Cuánto le queda después del primer sobrino?", "anotaciones": []},
    )
    salida = responder(ChatEntrada(mensaje="decime cuál es", contexto={"enunciado": BILLETERA.enunciado}))
    assert salida.texto == "¿Cuánto le queda después del primer sobrino?"


def test_las_opciones_y_la_clave_no_se_le_mandan_al_modelo(modelo, monkeypatch):
    secreto = ejercicio("secreto", BILLETERA.enunciado, opciones=("OPCION-CLAVE", "otra", "otra más", "ninguna"))
    secreto = secreto.model_copy(update={"comprobacion": "COMPROBACION-SECRETA"})
    monkeypatch.setattr(buscador, "obtener_buscador", lambda: Buscador([secreto]))
    modelo.responde({"texto": "¿Qué te piden?", "anotaciones": []})
    responder(ChatEntrada(mensaje="ayuda", contexto={"enunciado": BILLETERA.enunciado}))
    enviado = json.dumps(modelo.llamadas, ensure_ascii=False)
    assert "Paso de secreto." in enviado
    assert "OPCION-CLAVE" not in enviado and "COMPROBACION-SECRETA" not in enviado


def test_si_es_del_banco_tambien_bloquea_el_valor_de_la_clave(modelo, monkeypatch):
    con_valores = ejercicio("valores", BILLETERA.enunciado, clave="C", opciones=("200 colones", "100 colones", "50 colones", "25 colones"))
    monkeypatch.setattr(buscador, "obtener_buscador", lambda: Buscador([con_valores]))
    modelo.responde(
        {"texto": "Al cuarto le dio 50 colones.", "anotaciones": []},
        {"texto": "¿Cuánto le dio al primero?", "anotaciones": []},
    )
    salida = responder(ChatEntrada(mensaje="decime", contexto={"enunciado": BILLETERA.enunciado}))
    assert salida.texto == "¿Cuánto le dio al primero?"


def test_en_un_ejercicio_verbal_solo_cuenta_la_letra(modelo, monkeypatch):
    verbal = ejercicio("verbal", LECTURA.enunciado, clave="A", opciones=("Solo la 1.", "Solo la 2.", "Solo la 3.", "Ninguna."))
    verbal = verbal.model_copy(update={"area": "Razonamiento verbal"})
    monkeypatch.setattr(buscador, "obtener_buscador", lambda: Buscador([verbal]))
    modelo.responde({"texto": "Leé de nuevo la proposición 1. ¿Qué dice?", "anotaciones": []})
    salida = responder(ChatEntrada(mensaje="ayuda", contexto={"enunciado": LECTURA.enunciado}))
    assert salida.texto == "Leé de nuevo la proposición 1. ¿Qué dice?"
