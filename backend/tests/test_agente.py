"""Pruebas del agente: armado de la conversación y lectura de la respuesta del modelo."""

import json

import pytest

from app.esquemas import AnotacionApunte, AnotacionCirculo, AnotacionEnunciado, ChatEntrada
from app.servicios.agente import INSTRUCCIONES_DEL_TUTOR, RespuestaInvalida, armar_conversacion, interpretar_respuesta

ENUNCIADO = "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó el precio?"


# ---------- armar_conversacion ----------


def test_empieza_con_las_instrucciones_y_el_estado():
    entrada = ChatEntrada(mensaje="Dame una pista", contexto={"enunciado": ENUNCIADO, "pistas_dadas": 2})
    sistema = armar_conversacion(entrada)[0]
    assert sistema["role"] == "system"
    assert "Nunca des la respuesta final" in sistema["content"]
    assert f"Problema en la pizarra: {ENUNCIADO}" in sistema["content"]
    assert "Pistas ya dadas: 2" in sistema["content"]


def test_sin_problema_lo_dice():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "Problema en la pizarra: todavía no hay" in sistema


def test_las_instrucciones_prohiben_mae_y_pura_vida():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert 'Prohibido usar "mae" y "pura vida"' in sistema


def test_las_instrucciones_piden_voseo_sin_tuteo():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "Nunca tuteés" in sistema


def test_las_instrucciones_dicen_que_hacer_con_las_fotos():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "## Cuando llega una foto" in sistema
    assert "pedile que la tome de nuevo" in sistema
    assert "comentá su procedimiento" in sistema


def test_traduce_el_historial_a_roles_del_modelo():
    entrada = ChatEntrada(
        mensaje="creo que es 6000",
        historial=[
            {"autor": "estudiante", "texto": ENUNCIADO},
            {"autor": "tutor", "texto": "¿Qué te piden?", "pista": None},
            {"autor": "estudiante", "texto": "   "},
        ],
    )
    mensajes = armar_conversacion(entrada)
    assert [m["role"] for m in mensajes] == ["system", "user", "assistant", "user"]
    assert mensajes[-1]["content"] == "creo que es 6000"


def test_la_foto_va_como_imagen_con_su_tipo():
    entrada = ChatEntrada(mensaje="", imagen_base64="iVBORw0KGgoAAAA")
    ultimo = armar_conversacion(entrada)[-1]
    texto, imagen = ultimo["content"]
    assert texto["type"] == "text" and texto["text"]
    assert imagen["image_url"]["url"].startswith("data:image/png;base64,iVBOR")


def test_los_ejercicios_parecidos_van_solo_en_las_instrucciones():
    from app.esquemas import Ejercicio

    parecido = Ejercicio(
        id="x",
        tema="Porcentajes",
        area="Razonamiento matemático",
        enunciado="Un libro sube de 100 a 120. ¿Cuánto aumentó?",
        opciones=[],
        solucion={"tipo": "numero", "valor": "20"},
        pasos=["Restá los precios"],
        errores_comunes=["Dividir entre el precio nuevo"],
    )
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"), [parecido])[0]["content"]
    assert "solo para vos" in sistema
    assert "Error común: Dividir entre el precio nuevo" in sistema


# ---------- interpretar_respuesta ----------


def respuesta(**campos) -> str:
    return json.dumps({"texto": "¿Qué te piden?", "pista": None, "anotaciones": [], **campos}, ensure_ascii=False)


def test_lee_una_respuesta_completa():
    salida = interpretar_respuesta(
        respuesta(
            pista=1,
            anotaciones=[
                {"tipo": "enunciado", "texto": ENUNCIADO},
                {"tipo": "circulo", "dato": "₡40 000"},
                {"tipo": "apunte", "texto": "aumento = 46 000 − 40 000"},
            ],
        ),
        proveedor="gemini",
    )
    assert salida.pista == 1 and salida.proveedor == "gemini"
    assert [type(a) for a in salida.anotaciones] == [AnotacionEnunciado, AnotacionCirculo, AnotacionApunte]


@pytest.mark.parametrize("envoltorio", ["```json\n{}\n```", "```\n{}\n```", "Claro, aquí va: {} ¡Suerte!"])
def test_acepta_json_envuelto(envoltorio):
    texto = envoltorio.replace("{}", respuesta())
    assert interpretar_respuesta(texto, "groq").texto == "¿Qué te piden?"


@pytest.mark.parametrize("malo", ["no es json", "[1, 2]", '{"pista": 1}', '{"texto": "   "}', '{"texto": "a",'])
def test_rechaza_lo_que_no_sirve(malo):
    with pytest.raises(RespuestaInvalida):
        interpretar_respuesta(malo, "gemini")


def test_descarta_circulos_sobre_datos_que_no_estan_en_el_enunciado():
    salida = interpretar_respuesta(
        respuesta(anotaciones=[{"tipo": "circulo", "dato": "₡40 000"}, {"tipo": "circulo", "dato": "₡99 999"}]),
        "gemini",
        enunciado_actual=ENUNCIADO,
    )
    assert [a.dato for a in salida.anotaciones] == ["₡40 000"]


def test_sin_enunciado_no_hay_circulos():
    salida = interpretar_respuesta(respuesta(anotaciones=[{"tipo": "circulo", "dato": "40"}]), "gemini")
    assert salida.anotaciones == []


def test_como_maximo_cuatro_circulos():
    datos = ["₡40 000", "₡46 000", "porcentaje", "precio", "tenis"]
    salida = interpretar_respuesta(
        respuesta(anotaciones=[{"tipo": "circulo", "dato": d} for d in datos]), "gemini", enunciado_actual=ENUNCIADO
    )
    assert len(salida.anotaciones) == 4


def test_descarta_anotaciones_mal_formadas_sin_perder_las_buenas():
    salida = interpretar_respuesta(
        respuesta(
            anotaciones=[
                {"tipo": "dibujo", "texto": "x"},
                {"tipo": "apunte", "texto": "x" * 500},
                "texto suelto",
                {"tipo": "apunte", "texto": "datos: 40 000 y 46 000"},
            ]
        ),
        "gemini",
    )
    assert [a.texto for a in salida.anotaciones] == ["datos: 40 000 y 46 000"]


@pytest.mark.parametrize("pista, esperado", [(1, 1), (5, 5), ("2", 2), (0, None), (21, None), (True, None), ("x", None)])
def test_normaliza_el_numero_de_pista(pista, esperado):
    assert interpretar_respuesta(respuesta(pista=pista), "gemini").pista == esperado


def test_no_vuelve_a_copiar_el_mismo_enunciado():
    repetido = ENUNCIADO.replace(" ", "  ").upper()
    salida = interpretar_respuesta(
        respuesta(anotaciones=[{"tipo": "enunciado", "texto": repetido}, {"tipo": "circulo", "dato": "₡40 000"}]),
        "groq",
        enunciado_actual=ENUNCIADO,
    )
    assert [type(a) for a in salida.anotaciones] == [AnotacionCirculo]


def test_un_problema_nuevo_si_se_copia():
    otro = "Si 3x + 5 = 20, ¿cuánto vale x?"
    salida = interpretar_respuesta(
        respuesta(anotaciones=[{"tipo": "enunciado", "texto": otro}, {"tipo": "circulo", "dato": "20"}]),
        "gemini",
        enunciado_actual=ENUNCIADO,
    )
    assert [type(a) for a in salida.anotaciones] == [AnotacionEnunciado, AnotacionCirculo]


def test_recopiar_solo_la_ecuacion_tambien_es_el_mismo_problema():
    actual = "cual es el valor de x? 3x-5+20=50"
    salida = interpretar_respuesta(
        respuesta(anotaciones=[{"tipo": "enunciado", "texto": "3x - 5 + 20 = 50"}, {"tipo": "circulo", "dato": "50"}]),
        "groq",
        enunciado_actual=actual,
    )
    assert [type(a) for a in salida.anotaciones] == [AnotacionCirculo]


def test_las_instrucciones_definen_cuando_un_mensaje_es_una_pista():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "## Cuándo un mensaje es una pista" in sistema
    assert "probá primero con una pregunta abierta" in sistema
    assert 'El número de la pista es el de "Pistas ya dadas" más 1.' in sistema


def test_las_instrucciones_piden_seguir_al_estudiante_sin_adelantarse():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "Seguí el método y las palabras del estudiante" in sistema
    assert "Nunca le digás cuál es el paso siguiente si no te lo pidió" in sistema
    assert "Ejemplo de cómo seguir al estudiante sin adelantarte" in sistema
    assert "repetir o confirmar un paso que propuso el estudiante" in sistema
    assert "no instrucciones de qué hacer" in sistema


def test_las_instrucciones_piden_valorar_lo_que_dijo_el_estudiante():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "## Cada respuesta tiene dos partes" in sistema
    assert "Si está mal, decile que todavía no y por qué" in sistema
    assert "No le preguntés algo que ya respondió" in sistema
    assert "Revisá la ortografía" in sistema
    assert "confirmalo en pocas palabras" not in sistema


def test_las_instrucciones_prohiben_felicitar_sin_motivo():
    sistema = armar_conversacion(ChatEntrada(mensaje="hola"))[0]["content"]
    assert "Decí que está bien SOLO si de verdad está bien" in sistema
    assert "Si el estudiante solo mandó el problema, todavía no propuso nada" in sistema


@pytest.mark.parametrize(
    ("evaluacion", "texto", "queda"),
    [
        ("sin_propuesta", "¡Correcto! Necesitamos comparar las horas.", "Necesitamos comparar las horas."),
        ("incorrecto", "Bien, ya sabés que en 3 horas…", "Ya sabés que en 3 horas…"),
        ("incorrecto", "¡Muy bien! ¿Seguro?", "¿Seguro?"),
        ("a_medias", "¡Exacto, te piden el mínimo!", "Te piden el mínimo!"),
        ("a_medias", "¡Bien! La primera parte va. ¿Y la otra?", "¡Bien! La primera parte va. ¿Y la otra?"),
        ("correcto", "¡Exacto! Con 10 empleados alcanza.", "¡Exacto! Con 10 empleados alcanza."),
        (None, "¡Correcto!, sigamos.", "¡Correcto!, sigamos."),
        ("sin_propuesta", "Bienvenido, mandame un ejercicio.", "Bienvenido, mandame un ejercicio."),
    ],
)
def test_quita_la_felicitacion_si_el_propio_modelo_dice_que_no_acerto(evaluacion, texto, queda):
    crudo = json.dumps({"evaluacion": evaluacion, "texto": texto, "pista": None, "anotaciones": []})
    assert interpretar_respuesta(crudo, "groq").texto == queda


def test_las_instrucciones_piden_explicar_y_cerrar():
    assert "## Cuándo explicar" in INSTRUCCIONES_DEL_TUTOR
    assert "no entendí" in INSTRUCCIONES_DEL_TUTOR
    assert "practicar otro ejercicio" in INSTRUCCIONES_DEL_TUTOR
    assert '"evaluacion"' in INSTRUCCIONES_DEL_TUTOR


def test_las_instrucciones_no_preguntan_que_piden_ni_se_contestan_solas():
    assert "No le preguntés qué le piden" in INSTRUCCIONES_DEL_TUTOR
    assert "qué entiende que le piden" not in INSTRUCCIONES_DEL_TUTOR
    assert "No contestés tu propia pregunta" in INSTRUCCIONES_DEL_TUTOR


def test_en_lectura_la_conexion_la_hace_el_estudiante():
    assert "la conexión entre el texto y las\nopciones la hace el estudiante, nunca vos" in INSTRUCCIONES_DEL_TUTOR
    assert "buscá la que" in INSTRUCCIONES_DEL_TUTOR


def test_las_instrucciones_prohiben_usar_palabras_clave_de_las_opciones():
    assert "Tampoco usés las palabras clave de las opciones" in INSTRUCCIONES_DEL_TUTOR


def test_las_pistas_llevan_el_porque_y_no_hace_las_cuentas_del_estudiante():
    assert "siempre lleva la idea, no solo el paso" in INSTRUCCIONES_DEL_TUTOR
    assert "no lo sumés vos" in INSTRUCCIONES_DEL_TUTOR


def test_en_lectura_explica_el_metodo_con_un_ejemplo_inventado():
    assert "Si el estudiante no entiende qué tienen que ver las opciones con el texto" in INSTRUCCIONES_DEL_TUTOR
    assert "Nunca repitás la misma pregunta" in INSTRUCCIONES_DEL_TUTOR


def test_un_ejercicio_resuelto_no_vuelve_a_empezar():
    assert "5. Si te pide la respuesta y todavía no la dijo" in INSTRUCCIONES_DEL_TUTOR
    assert "el ejercicio está resuelto y no\n    volvés a empezar con pistas" in INSTRUCCIONES_DEL_TUTOR
    assert "si le quedó claro o si quiere que se lo expliqués de\n    otra manera" in INSTRUCCIONES_DEL_TUTOR
