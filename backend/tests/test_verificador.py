"""Pruebas del verificador: cálculo de la respuesta, comparación y detección de filtraciones."""

import time
from fractions import Fraction

import pytest

from app.esquemas import ChatEntrada, ChatSalida, Solucion
from app.servicios.verificador import (
    Esperada,
    es_equivalente,
    filtra_la_respuesta,
    resolver_enunciado,
    respuesta_esperada,
    revela_solucion,
)

# ---------- resolver_enunciado ----------


@pytest.mark.parametrize(
    "enunciado, esperado",
    [
        ("Si 3x + 5 = 20, ¿cuánto vale x?", [Fraction(5)]),
        ("cual es el valor de x? 3x-5+20=50", [Fraction(35, 3)]),
        ("Resolvé: 2(x − 3) = 10", [Fraction(8)]),
        ("Hallá n si n/4 = 2,5", [Fraction(10)]),
        ("Calcule: 3x = 6", [Fraction(2)]),
        ("x^2 = 9, ¿cuáles son los valores de x?", [Fraction(-3), Fraction(3)]),
        ("Si 3x + 5 = 20 y luego sumás 2, ¿cuánto vale x?", [Fraction(5)]),
        ("¿Cuánto es 6000 ÷ 40 000?", [Fraction(3, 20)]),
        ("¿cuánto es 1.500 × 2?", [Fraction(3000)]),
    ],
)
def test_calcula_lo_que_se_puede_calcular(enunciado, esperado):
    assert sorted(resolver_enunciado(enunciado)) == esperado


@pytest.mark.parametrize(
    "enunciado",
    [
        "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó el precio?",
        "¿Qué número sigue en la sucesión 2, 6, 12, 20, 30?",
        "x + y = 10",
        "¿Cuánto es 5?",
        "hola",
        "",
    ],
)
def test_no_inventa_cuando_no_se_puede_calcular(enunciado):
    assert resolver_enunciado(enunciado) == []


@pytest.mark.parametrize(
    "peligroso",
    [
        "__import__('os').system('ls') = 1",
        "x = 9^9^9^9",
        "x^999999 = 1",
        "x = " + "9" * 500,
    ],
)
def test_no_evalua_texto_peligroso(peligroso):
    inicio = time.time()
    assert resolver_enunciado(peligroso) == []
    assert time.time() - inicio < 2


def test_los_nombres_de_funciones_nunca_llegan_a_sympy():
    from app.servicios.verificador import _a_sympy, _corridas_matematicas

    # El filtro corta las palabras: de "open(x) = 2" solo queda la ecuación inofensiva "(x) = 2".
    assert _corridas_matematicas("open(x) = 2") == ["(x) = 2"]
    assert all("import" not in c and "system" not in c for c in _corridas_matematicas("__import__('os').system('ls') = 1"))
    # Y aunque alguien llamara a _a_sympy directamente con un nombre, lo rechaza.
    for texto in ("open(x)", "__import__(x)", "exec(1)", "os.system(1)", "x.y"):
        assert _a_sympy(texto) is None


def test_un_texto_largo_lleno_de_numeros_no_lo_cuelga():
    inicio = time.time()
    resolver_enunciado("1 000 000 " * 200)
    assert time.time() - inicio < 2


# ---------- respuesta_esperada ----------


def test_la_solucion_del_banco_manda():
    esperada = respuesta_esperada("Si 3x + 5 = 20", Solucion(tipo="numero", valor="15 %"))
    assert esperada == Esperada(valores=[Fraction(15)], es_porcentaje=True)


def test_opcion_con_letra():
    assert respuesta_esperada(None, Solucion(tipo="opcion", valor="c")) == Esperada(letra="C")


def test_sin_banco_y_sin_calculo_no_hay_respuesta():
    assert respuesta_esperada("¿Qué número sigue en 2, 6, 12?") is None


# ---------- es_equivalente ----------

QUINCE_PORCIENTO = Esperada(valores=[Fraction(15)], es_porcentaje=True)
CINCO = Esperada(valores=[Fraction(5)])


@pytest.mark.parametrize("propuesta", ["15 %", "15%", "da 0,15", "0.15", "creo que es 15", "15 por ciento", "3/20"])
def test_acepta_las_formas_de_decir_15_por_ciento(propuesta):
    assert es_equivalente(propuesta, QUINCE_PORCIENTO)


@pytest.mark.parametrize("propuesta", ["13 %", "0,13", "150", "1,5", "no sé"])
def test_rechaza_lo_que_no_es_15_por_ciento(propuesta):
    assert not es_equivalente(propuesta, QUINCE_PORCIENTO)


def test_un_numero_sin_porcentaje_no_es_un_porcentaje():
    assert es_equivalente("x = 5", CINCO)
    assert not es_equivalente("5 %", CINCO)


def test_acepta_la_letra_de_la_opcion():
    c = Esperada(letra="C")
    assert es_equivalente("creo que es la C", c) and es_equivalente("c", c) and es_equivalente("opción c)", c)
    assert not es_equivalente("la B", c) and not es_equivalente("cuánto es", c)


def test_acepta_decimales_redondeados():
    treinta_y_cinco_tercios = Esperada(valores=[Fraction(35, 3)])
    assert es_equivalente("me da 11,67", treinta_y_cinco_tercios)
    assert es_equivalente("11.6", treinta_y_cinco_tercios)
    assert not es_equivalente("12", treinta_y_cinco_tercios)


# ---------- revela_solucion ----------

ECUACION = "Si 3x + 5 = 20, ¿cuánto vale x?"  # respuesta: 5, que también es un dato del problema


@pytest.mark.parametrize(
    "texto",
    ["Entonces x = 5.", "El resultado es 5", "Te da 5, ¿ves?", "La respuesta: 5", "x vale 5"],
)
def test_detecta_la_respuesta_presentada_como_resultado(texto):
    assert revela_solucion(texto, CINCO, ECUACION)


@pytest.mark.parametrize(
    "texto",
    [
        "Restá 5 a ambos lados. ¿Qué te queda?",
        "Fijate en el 5 que está sumando.",
        "3x + 5 = 20",
        "3x = 20 − 5",
        "Primero quitá el 5: 3x = 15. ¿Y ahora?",
        "¿Cuánto es 15 ÷ 3?",
    ],
)
def test_mencionar_un_dato_del_problema_no_es_filtrar(texto):
    assert not revela_solucion(texto, CINCO, ECUACION)


def test_restar_un_dato_no_es_un_numero_negativo():
    # En "3x - 5 = 10" la respuesta es 5; decir "sumá 5" usa un dato, no la regala.
    assert not revela_solucion("Sumá 5 a ambos lados.", CINCO, "3x - 5 = 10")
    assert revela_solucion("Entonces x = 5", CINCO, "3x - 5 = 10")


def test_si_la_respuesta_no_es_un_dato_cualquier_mencion_es_filtrar():
    ocho = Esperada(valores=[Fraction(8)])
    assert revela_solucion("Pensá en el 8.", ocho, "2(x − 3) = 10")
    assert not revela_solucion("Dividí 10 entre 2.", ocho, "2(x − 3) = 10")


def test_detecta_la_letra_de_la_opcion():
    c = Esperada(letra="C")
    assert revela_solucion("Es la opción C.", c)
    assert not revela_solucion("Compará las opciones con calma.", c)


# ---------- filtra_la_respuesta ----------


def entrada(mensaje: str, historial=(), enunciado: str | None = ECUACION) -> ChatEntrada:
    return ChatEntrada(mensaje=mensaje, historial=list(historial), contexto={"enunciado": enunciado})


def test_bloquea_cuando_el_tutor_regala_el_resultado():
    assert filtra_la_respuesta(ChatSalida(texto="Fácil: x = 5."), entrada("Decime la respuesta"))


def test_bloquea_cuando_el_resultado_va_en_un_apunte():
    salida = ChatSalida(texto="Fijate en la pizarra.", anotaciones=[{"tipo": "apunte", "texto": "x = 15 ÷ 3 = 5"}])
    assert filtra_la_respuesta(salida, entrada("no entiendo"))


def test_deja_pasar_una_pista_que_usa_los_datos():
    salida = ChatSalida(texto="Restá 5 a ambos lados. ¿Qué te queda?", pista=1, anotaciones=[{"tipo": "apunte", "texto": "3x = 20 − 5"}])
    assert not filtra_la_respuesta(salida, entrada("Dame una pista"))


def test_puede_confirmar_si_el_estudiante_ya_la_dijo():
    confirmacion = ChatSalida(texto="¡Exacto! x = 5 porque 15 ÷ 3 = 5.")
    assert not filtra_la_respuesta(confirmacion, entrada("me dio x = 5"))
    assert not filtra_la_respuesta(confirmacion, entrada("5"))
    antes = [{"autor": "estudiante", "texto": "creo que x = 5"}, {"autor": "tutor", "texto": "¿Por qué?"}]
    assert not filtra_la_respuesta(confirmacion, entrada("porque dividí 15 entre 3", antes))


def test_el_enunciado_del_estudiante_no_cuenta_como_que_ya_la_dijo():
    # El primer mensaje trae el 5 como dato; eso no autoriza a dar la respuesta.
    historial = [{"autor": "estudiante", "texto": ECUACION}]
    assert filtra_la_respuesta(ChatSalida(texto="La respuesta es 5."), entrada("no sé", historial))


def test_usa_el_enunciado_que_el_tutor_acaba_de_copiar():
    salida = ChatSalida(texto="Listo: x = 5.", anotaciones=[{"tipo": "enunciado", "texto": ECUACION}])
    assert filtra_la_respuesta(salida, entrada(ECUACION, enunciado=None))


def test_sin_respuesta_conocida_no_bloquea():
    tenis = "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó?"
    assert not filtra_la_respuesta(ChatSalida(texto="Es 15 %."), entrada("decime", enunciado=tenis))


def test_con_la_solucion_del_banco_si_bloquea():
    tenis = "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó?"
    solucion = Solucion(tipo="numero", valor="15 %")
    assert filtra_la_respuesta(ChatSalida(texto="Es 15 %."), entrada("decime", enunciado=tenis), solucion)
    assert filtra_la_respuesta(ChatSalida(texto="Dividí y te da 0,15."), entrada("decime", enunciado=tenis), solucion)
    assert not filtra_la_respuesta(ChatSalida(texto="¿Cuánto subió en colones?"), entrada("decime", enunciado=tenis), solucion)


# ---------- Clave de selección con valor ----------

SOBRINOS = (
    "Carlos tenía 800 gapes. A cada sobrino que llegaba le regalaba la mitad de lo que tenía. "
    "¿Cuánto le dio al cuarto sobrino?"
)
OPCIONES_SOBRINOS = ["200 gapes", "100 gapes", "50 gapes", "25 gapes"]
CLAVE_C = Solucion(tipo="opcion", valor="C")


@pytest.mark.parametrize(
    ("opcion", "valor"),
    [("50 gapes", Fraction(50)), ("3 000", Fraction(3000)), ("65 + 16²", Fraction(321)), ("25/3", Fraction(25, 3))],
)
def test_la_clave_tambien_se_reconoce_por_su_valor(opcion, valor):
    esperada = respuesta_esperada(None, Solucion(tipo="opcion", valor="A"), [opcion, "otra"])
    assert esperada == Esperada(valores=[valor], letra="A")


@pytest.mark.parametrize(
    "opcion",
    ["Martes.", "S₁₀ + 23", "Se empacaron más de 40 bombillos defectuosos.", "Entre 3 y 5 horas."],
)
def test_una_frase_o_una_expresion_con_incognitas_solo_cuenta_por_la_letra(opcion):
    assert respuesta_esperada(None, Solucion(tipo="opcion", valor="A"), [opcion, "otra"]) == Esperada(letra="A")


def test_bloquea_el_valor_de_la_opcion_correcta():
    pregunta = entrada("decime", enunciado=SOBRINOS)
    assert filtra_la_respuesta(ChatSalida(texto="Al cuarto le dio 50 gapes."), pregunta, CLAVE_C, OPCIONES_SOBRINOS)
    assert filtra_la_respuesta(ChatSalida(texto="Es la C."), pregunta, CLAVE_C, OPCIONES_SOBRINOS)


def test_deja_pasar_los_valores_de_las_otras_opciones_y_los_pasos():
    pregunta = entrada("no entiendo", enunciado=SOBRINOS)
    pista = ChatSalida(texto="Al primero le dio 400. ¿Cuánto le queda para el segundo?", anotaciones=[{"tipo": "apunte", "texto": "800 ÷ 2 = 400"}])
    assert not filtra_la_respuesta(pista, pregunta, CLAVE_C, OPCIONES_SOBRINOS)
    assert not filtra_la_respuesta(ChatSalida(texto="¿Por qué 100 no puede ser?"), pregunta, CLAVE_C, OPCIONES_SOBRINOS)


def test_puede_confirmar_si_el_estudiante_dijo_el_valor():
    confirmacion = ChatSalida(texto="¡Eso! 50 gapes, la C.")
    assert not filtra_la_respuesta(confirmacion, entrada("me dio 50", enunciado=SOBRINOS), CLAVE_C, OPCIONES_SOBRINOS)
