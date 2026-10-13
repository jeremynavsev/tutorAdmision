"""Pruebas del contrato de POST /api/chat."""

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


RESPUESTA = {"texto": "¿Qué te piden?", "pista": None, "anotaciones": []}


def test_responde_con_el_contrato(modelo):
    modelo.responde({"texto": "Restá 5 a ambos lados.", "pista": 2, "anotaciones": [{"tipo": "apunte", "texto": "3x = 20 − 5"}]})
    respuesta = cliente.post(
        "/api/chat",
        json={
            "mensaje": "Dame una pista",
            "historial": [{"autor": "tutor", "texto": "Mandame el problema.", "pista": None}],
            "contexto": {"enunciado": "Si 3x + 5 = 20, ¿cuánto vale x?", "pistas_dadas": 1},
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "texto": "Restá 5 a ambos lados.",
        "pista": 2,
        "anotaciones": [{"tipo": "apunte", "texto": "3x = 20 − 5"}],
        "proveedor": "falso",
    }


def test_basta_con_el_mensaje(modelo):
    modelo.responde(RESPUESTA)
    assert cliente.post("/api/chat", json={"mensaje": "hola"}).status_code == 200


def test_basta_con_una_foto(modelo):
    import base64
    import io

    from PIL import Image

    modelo.responde(RESPUESTA)
    salida = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(salida, "PNG")
    foto = base64.b64encode(salida.getvalue()).decode()
    assert cliente.post("/api/chat", json={"imagen_base64": foto}).status_code == 200


def test_una_foto_que_no_es_imagen_devuelve_400_con_mensaje(modelo):
    respuesta = cliente.post("/api/chat", json={"imagen_base64": "aGVsbG8="})
    assert respuesta.status_code == 400
    assert "no es una imagen válida" in respuesta.json()["detail"]
    assert modelo.llamadas == []


def test_sin_proveedores_devuelve_503_con_mensaje_amable():
    respuesta = cliente.post("/api/chat", json={"mensaje": "hola"})
    assert respuesta.status_code == 503
    assert "no está disponible" in respuesta.json()["detail"]


def test_si_el_modelo_no_da_json_devuelve_503(modelo):
    modelo.responde("nada", "tampoco")
    assert cliente.post("/api/chat", json={"mensaje": "hola"}).status_code == 503


def test_los_errores_no_muestran_detalles_internos():
    cuerpo = cliente.post("/api/chat", json={"mensaje": "hola"}).text
    assert "prueba:" not in cuerpo and "HTTP" not in cuerpo and "Traceback" not in cuerpo


def test_rechaza_mensaje_vacio_sin_foto():
    assert cliente.post("/api/chat", json={"mensaje": "   "}).status_code == 422


def test_las_pistas_no_tienen_tope_de_tres(modelo):
    modelo.responde(RESPUESTA)
    entrada = {"mensaje": "hola", "historial": [{"autor": "tutor", "texto": "x", "pista": 7}]}
    assert cliente.post("/api/chat", json=entrada).status_code == 200


def test_rechaza_numero_de_pista_fuera_de_rango():
    for pista in (0, 21):
        entrada = {"mensaje": "hola", "historial": [{"autor": "tutor", "texto": "x", "pista": pista}]}
        assert cliente.post("/api/chat", json=entrada).status_code == 422


def test_rechaza_historial_demasiado_largo():
    historial = [{"autor": "estudiante", "texto": "x"}] * 41
    assert cliente.post("/api/chat", json={"mensaje": "hola", "historial": historial}).status_code == 422


def test_las_anotaciones_se_distinguen_por_tipo():
    from app.esquemas import ChatSalida

    salida = ChatSalida.model_validate(
        {
            "texto": "Listo, ya lo copié.",
            "anotaciones": [
                {"tipo": "enunciado", "texto": "Si 3x + 5 = 20, ¿cuánto vale x?"},
                {"tipo": "circulo", "dato": "20"},
                {"tipo": "apunte", "texto": "1. ¿Qué me dan?"},
            ],
        }
    )
    assert [type(a).__name__ for a in salida.anotaciones] == ["AnotacionEnunciado", "AnotacionCirculo", "AnotacionApunte"]
