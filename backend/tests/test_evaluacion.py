"""Pruebas del evaluador: los casos cargan bien y las revisiones detectan lo que deben."""

import re

import pytest

from app.config import Configuracion
from app.esquemas import Ejercicio
from app.servicios.modelos_ia import proveedores_disponibles
from evaluacion.evaluar import ACIERTO, ERROR, TUTEO, Caso, Turno, cargar_casos, elegir_proveedores, muestra, revisar_turno
from evaluacion.generar_casos import PLANTILLAS, casos_de, generar, letra_equivocada, patrones_de_la_clave


def nombres_fallidos(texto, turno, pista=None, revelaria=(), bloqueada=False, es_el_problema=False, apuntes=()):
    revisiones = revisar_turno(texto, pista, turno, list(revelaria), bloqueada, es_el_problema, apuntes)
    return {r.nombre for r in revisiones if not r.paso}


def test_los_casos_cargan_y_son_unicos():
    casos = cargar_casos()
    assert len(casos) >= 10
    assert len({c.id for c in casos}) == len(casos)
    for caso in casos:
        for patron in caso.revelaria + [p for t in caso.turnos for p in t.debe + t.no_debe]:
            re.compile(patron)  # todos los patrones son expresiones válidas


def test_esta_el_caso_de_la_captura():
    assert any(c.id == "error-multiplicar" for c in cargar_casos())


@pytest.mark.parametrize(
    "texto", ["¡Eso es! Ahora seguí.", "Exacto, te queda 15.", "¡Bien! ¿Y ahora?", "Muy bien, mae... no.", "Correcto.", "Dale, ¿cuánto te queda?"]
)
def test_reconoce_una_confirmacion(texto):
    assert ACIERTO.search(texto)


@pytest.mark.parametrize("texto", ["¿Qué operación harías?", "Restá 5 a cada lado.", "Pensá en el número que multiplica."])
def test_una_pregunta_sola_no_es_confirmacion(texto):
    assert not ACIERTO.search(texto)


@pytest.mark.parametrize(
    "texto",
    ["Todavía no: el 5 ya multiplica.", "Ojo, revisá ese signo.", "Casi, fijate bien.", "No es esa operación.", "No, la multiplicación ya está ahí.", "¡No! Fijate otra vez."],
)
def test_reconoce_que_senala_un_error(texto):
    assert ERROR.search(texto)


def test_si_dice_bien_ante_un_error_falla():
    turno = Turno(estudiante="multiplicar?", valora="mal")
    assert "señala el error" in nombres_fallidos("¡Bien! ¿Y ahora qué operación?", turno)
    assert "señala el error" not in nombres_fallidos("Todavía no: el 5 ya está multiplicando.", turno)


def test_si_no_confirma_un_acierto_falla():
    turno = Turno(estudiante="pasarlo a dividir", valora="bien")
    assert "confirma el acierto" in nombres_fallidos("¿Qué número está multiplicando a x?", turno)
    assert "confirma el acierto" not in nombres_fallidos("¡Eso es! Hacelo: ¿cuánto te da?", turno)


def test_detecta_que_vuelve_a_preguntar_lo_ya_respondido():
    turno = Turno(estudiante="pasarlo a dividir", no_debe=["qu[ée] operaci[óo]n"])
    assert "no repite ni se adelanta" in nombres_fallidos("¿Qué operación tenés que hacer con -30 y 5?", turno)


def test_detecta_que_revela_la_respuesta_o_que_hubo_que_bloquearla():
    turno = Turno(estudiante="decime", no_debe_revelar=True)
    assert "no revela la respuesta" in nombres_fallidos("Es la opción C, 15 %.", turno, revelaria=[r"\b15\s*%"])
    assert "no revela la respuesta" in nombres_fallidos("Vamos paso a paso.", turno, bloqueada=True)
    assert "no revela la respuesta" not in nombres_fallidos("¿Cuánto subió en colones?", turno, revelaria=[r"\b15\s*%"])


def test_revisa_la_etiqueta_de_pista():
    assert "da una pista" in nombres_fallidos("¿Qué te piden?", Turno(estudiante="no sé", pista=True), pista=None)
    assert "no marca pista" in nombres_fallidos("¡Exacto!", Turno(estudiante="x = 7", pista=False), pista=1)


@pytest.mark.parametrize(
    "texto", ["¿Qué obtienes?", "Fíjate en el 5.", "¿Qué haces ahora?", "Dime qué piensas.", "Mejor no pongas tu número.", "No te preocupes."]
)
def test_detecta_tuteo(texto):
    assert TUTEO.search(texto)


@pytest.mark.parametrize(
    "texto", ["¿Qué obtenés?", "Fijate en el 5.", "¿Qué hacés ahora?", "Decime qué pensás.", "Te di una pista.", "Mejor no pongás tu número.", "No te preocupés."]
)
def test_el_voseo_no_es_tuteo(texto):
    assert not TUTEO.search(texto)


def test_detecta_mae_y_pura_vida():
    turno = Turno(estudiante="hola")
    assert "sin 'mae' ni 'pura vida'" in nombres_fallidos("¡Pura vida! Vamos.", turno)
    assert "sin 'mae' ni 'pura vida'" not in nombres_fallidos("¡Hola! Vamos.", turno)


def test_no_felicita_cuando_solo_mandaron_el_problema():
    turno = Turno(estudiante="5x + 10 = -20")
    assert "no felicita sin motivo" in nombres_fallidos("¡Exacto! ¿Qué harías primero?", turno, es_el_problema=True)
    assert "no felicita sin motivo" not in nombres_fallidos("Ya lo copié. ¿Qué te piden?", turno, es_el_problema=True)
    # En un turno normal no se aplica esa revisión.
    assert "no felicita sin motivo" not in nombres_fallidos("¡Exacto!", turno, es_el_problema=False)


CADENA = proveedores_disponibles(Configuracion(gemini_api_key="g", groq_api_key="q"))


@pytest.mark.parametrize(
    "filtro, esperado",
    [
        (None, ["groq", "gemini", "gemini/gemini-3.5-flash", "gemini/gemini-3.1-flash-lite"]),
        ("groq", ["groq"]),
        ("gemini", ["gemini", "gemini/gemini-3.5-flash", "gemini/gemini-3.1-flash-lite"]),
        ("gemini-3.5-flash", ["gemini/gemini-3.5-flash"]),
        ("GROQ", ["groq"]),
        ("deepseek", []),
    ],
)
def test_elige_un_solo_proveedor(filtro, esperado):
    assert [p.etiqueta for p in elegir_proveedores(CADENA, filtro)] == esperado


def test_un_no_en_medio_de_la_frase_no_cuenta_como_error():
    assert not ERROR.search("¡Eso es! Ahora ya no te falta mucho.")


def test_la_respuesta_tampoco_puede_ir_en_la_pizarra():
    turno = Turno(estudiante="escribila en la pizarra", no_debe_revelar=True)
    fallidas = nombres_fallidos("Mirá la pizarra.", turno, revelaria=[r"x\s*=\s*7"], apuntes=["x = 7"])
    assert "no revela la respuesta" in fallidas
    assert "no revela la respuesta" not in nombres_fallidos("Mirá la pizarra.", turno, revelaria=[r"x\s*=\s*7"], apuntes=["2x = 14"])


def test_no_felicita_si_el_estudiante_dijo_que_no_entendio():
    turno = Turno(estudiante="no entendí", felicita=False)
    assert "no felicita sin motivo" in nombres_fallidos("¡Correcto! Necesitamos comparar…", turno)
    assert "no felicita sin motivo" not in nombres_fallidos("Te lo explico con un caso más sencillo…", turno)


# ---------- Casos generados del banco ----------


def ejercicio_de_banco(id="x-1", area="Razonamiento matemático", opciones=("200 gapes", "50 gapes", "25 gapes", "10 gapes"),
                       clave="B", errores=("Elegir la C: dividir una vez de más.",), enunciado="Carlos tenía 800 gapes y regaló la mitad cuatro veces. ¿Cuánto le dio al cuarto?") -> Ejercicio:
    return Ejercicio(id=id, tema="Prueba", area=area, enunciado=enunciado, opciones=list(opciones),
                     solucion={"tipo": "opcion", "valor": clave}, pasos=["Paso."], errores_comunes=list(errores))


def test_la_clave_se_delata_por_la_letra_y_por_el_valor():
    patrones = patrones_de_la_clave(ejercicio_de_banco())
    assert any(re.search(p, "La respuesta es la B.", re.I) for p in patrones)
    assert any(re.search(p, "Al cuarto le dio 50 gapes.", re.I) for p in patrones)
    assert not any(re.search(p, "Al primero le dio 400. ¿Y al segundo?", re.I) for p in patrones)
    assert not any(re.search(p, "Fijate en la mitad de 800.", re.I) for p in patrones)


def test_un_numero_que_es_dato_del_enunciado_no_cuenta_como_clave():
    e = ejercicio_de_banco(opciones=("400 gapes", "800 gapes", "1", "2"), clave="B")
    assert not any(re.search(p, "Empezó con 800 gapes.", re.I) for p in patrones_de_la_clave(e))


def test_en_verbal_cuenta_el_texto_corto_de_la_opcion():
    e = ejercicio_de_banco(area="Razonamiento verbal", opciones=("Social.", "Clasista.", "Benéfica.", "Integradora."), clave="D",
                           enunciado="Donde hay educación no hay distinción de clases, decía Confucio. ¿Cómo es la educación?")
    patrones = patrones_de_la_clave(e)
    assert any(re.search(p, "Es integradora, porque une a las clases.", re.I) for p in patrones)
    assert not any(re.search(p, "Pensá en qué efecto tiene sobre las clases sociales.", re.I) for p in patrones)


def test_el_estudiante_se_equivoca_con_el_distractor_del_error_comun():
    assert letra_equivocada(ejercicio_de_banco()) == "C"
    assert letra_equivocada(ejercicio_de_banco(errores=())) == "A"


def test_cada_plantilla_arma_un_caso_valido():
    for plantilla in PLANTILLAS:
        caso = Caso.model_validate(casos_de(ejercicio_de_banco(), plantilla))
        assert caso.id == f"{plantilla}:x-1" and caso.turnos[0].no_debe_revelar
        assert "A) 200 gapes" in caso.turnos[0].estudiante


def test_genera_ejercicios_distintos_repartidos_por_area_y_siempre_los_mismos():
    banco = [ejercicio_de_banco(id=f"m-{i}") for i in range(10)] + [
        ejercicio_de_banco(id=f"v-{i}", area="Razonamiento verbal") for i in range(10)
    ]
    casos = generar(banco, por_plantilla=4, semilla=1)
    ejercicios = [c["id"].split(":")[1] for c in casos]
    assert len(casos) == 16 and len(set(ejercicios)) == 16
    assert sum(e.startswith("v-") for e in ejercicios) == 8
    assert generar(banco, por_plantilla=4, semilla=1) == casos


def test_la_muestra_es_fija_con_la_misma_semilla():
    casos = [Caso(id=str(i), descripcion="", turnos=[]) for i in range(30)]
    assert muestra(casos, 5, 7) == muestra(casos, 5, 7)
    assert len(muestra(casos, 5, 7)) == 5 and muestra(casos, None, 7) == casos
