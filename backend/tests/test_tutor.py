"""Pruebas del tutor completo, con un modelo falso."""

import base64
import io

import pytest
from PIL import Image

from app.esquemas import ChatEntrada, Solucion
from app.servicios.agente import RespuestaInvalida
from app.servicios.imagenes import ImagenInvalida
from app.servicios.modelos_ia import SinProveedores
from app.servicios.tutor import RESPUESTA_SEGURA, responder

ECUACION = "Si 3x + 5 = 20, ¿cuánto vale x?"
PISTA = {"texto": "Restá 5 a ambos lados. ¿Qué te queda?", "pista": 1, "anotaciones": [{"tipo": "apunte", "texto": "3x = 20 − 5"}]}
FILTRACION = {"texto": "Es fácil: x = 5.", "pista": None, "anotaciones": []}


def entrada(mensaje="Dame una pista", **extra) -> ChatEntrada:
    return ChatEntrada(mensaje=mensaje, contexto={"enunciado": ECUACION, "pistas_dadas": 0}, **extra)


def foto(ancho=3000, alto=2000) -> str:
    exif = Image.Exif()
    exif[0x010F] = "MarcaDelCelular"
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), "gray").save(salida, "JPEG", exif=exif)
    return base64.b64encode(salida.getvalue()).decode()


def test_devuelve_la_respuesta_del_modelo(modelo):
    modelo.responde(PISTA)
    salida = responder(entrada())
    assert (salida.texto, salida.pista, salida.proveedor) == (PISTA["texto"], 1, "falso")
    assert salida.anotaciones[0].texto == "3x = 20 − 5"
    assert len(modelo.llamadas) == 1


def test_el_modelo_recibe_instrucciones_estado_y_mensaje(modelo):
    modelo.responde(PISTA)
    responder(entrada("no entiendo"))
    mensajes = modelo.llamadas[0]
    assert mensajes[0]["role"] == "system" and ECUACION in mensajes[0]["content"]
    assert mensajes[-1] == {"role": "user", "content": "no entiendo"}


def test_si_el_json_no_sirve_pide_otra_vez(modelo):
    modelo.responde("esto no es json", PISTA)
    assert responder(entrada()).texto == PISTA["texto"]
    assert len(modelo.llamadas) == 2


def test_si_el_json_falla_dos_veces_se_rinde(modelo):
    modelo.responde("nada", "tampoco")
    with pytest.raises(RespuestaInvalida):
        responder(entrada())


def test_si_filtra_el_resultado_pide_otra_respuesta_con_aviso(modelo):
    modelo.responde(FILTRACION, PISTA)
    salida = responder(entrada("Decime la respuesta"))
    assert salida.texto == PISTA["texto"]
    segunda = modelo.llamadas[1]
    assert segunda[-2] == {"role": "assistant", "content": FILTRACION["texto"]}
    assert "resultado final" in segunda[-1]["content"] and segunda[-1]["role"] == "user"


def test_si_insiste_en_filtrar_manda_la_respuesta_segura(modelo):
    modelo.responde(FILTRACION, {"texto": "Bueno, la respuesta es 5.", "anotaciones": []})
    salida = responder(entrada("Decime la respuesta"))
    assert salida.texto == RESPUESTA_SEGURA
    assert salida.anotaciones == [] and salida.pista is None


def test_si_el_segundo_intento_falla_tambien_manda_la_respuesta_segura(modelo):
    modelo.responde(FILTRACION, SinProveedores(["falso: HTTP 503"]))
    assert responder(entrada("Decime la respuesta")).texto == RESPUESTA_SEGURA


def test_nunca_sale_un_apunte_con_el_resultado(modelo):
    con_apunte = {"texto": "Mirá la pizarra.", "anotaciones": [{"tipo": "apunte", "texto": "x = 15 ÷ 3 = 5"}]}
    modelo.responde(con_apunte, con_apunte)
    salida = responder(entrada("no entiendo"))
    assert salida.texto == RESPUESTA_SEGURA and salida.anotaciones == []


def test_puede_confirmar_cuando_el_estudiante_ya_acerto(modelo):
    confirmacion = {"texto": "¡Exacto! x = 5.", "anotaciones": []}
    modelo.responde(confirmacion)
    assert responder(entrada("me dio x = 5")).texto == "¡Exacto! x = 5."
    assert len(modelo.llamadas) == 1


def test_con_la_solucion_del_banco_tambien_bloquea(modelo):
    tenis = "Unas tenis costaban ₡40 000 y ahora cuestan ₡46 000. ¿En qué porcentaje aumentó?"
    modelo.responde({"texto": "Aumentó 15 %.", "anotaciones": []}, {"texto": "¿Cuánto subió en colones?", "anotaciones": []})
    salida = responder(
        ChatEntrada(mensaje="decime", contexto={"enunciado": tenis}), solucion=Solucion(tipo="numero", valor="15 %")
    )
    assert salida.texto == "¿Cuánto subió en colones?"


def test_la_foto_llega_al_modelo_limpia_y_reducida(modelo):
    modelo.responde({"texto": "Ya copié el ejercicio.", "anotaciones": []})
    original = foto()
    responder(ChatEntrada(mensaje="", imagen_base64=original))
    url = modelo.llamadas[0][-1]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    enviada = base64.b64decode(url.split(",", 1)[1])
    assert b"MarcaDelCelular" not in enviada
    assert max(Image.open(io.BytesIO(enviada)).size) == 1600


def test_una_foto_invalida_no_llega_al_modelo(modelo):
    with pytest.raises(ImagenInvalida):
        responder(ChatEntrada(mensaje="", imagen_base64=base64.b64encode(b"no soy una imagen").decode()))
    assert modelo.llamadas == []


def test_sin_proveedores_avisa():
    with pytest.raises(SinProveedores):
        responder(entrada())


@pytest.mark.parametrize("pistas_dadas, numero_del_modelo, esperado", [(0, 5, 1), (2, 1, 3), (3, 4, 4), (19, 2, 20), (25, 1, 20)])
def test_el_numero_de_pista_sale_del_contador_no_del_modelo(modelo, pistas_dadas, numero_del_modelo, esperado):
    modelo.responde({"texto": "Restá 5 a ambos lados.", "pista": numero_del_modelo, "anotaciones": []})
    salida = responder(ChatEntrada(mensaje="ayuda", contexto={"enunciado": ECUACION, "pistas_dadas": pistas_dadas}))
    assert salida.pista == esperado


def test_si_no_es_pista_se_queda_sin_numero(modelo):
    modelo.responde({"texto": "¿Qué operación harías primero?", "pista": None, "anotaciones": []})
    assert responder(ChatEntrada(mensaje="hola", contexto={"enunciado": ECUACION, "pistas_dadas": 3})).pista is None
