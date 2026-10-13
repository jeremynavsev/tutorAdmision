"""Pruebas del contrato de POST /api/chat."""

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_responde_con_el_contrato():
    respuesta = cliente.post(
        "/api/chat",
        json={
            "mensaje": "Dame una pista",
            "historial": [{"autor": "tutor", "texto": "Mandame el problema.", "pista": None}],
            "contexto": {"enunciado": "Si 3x + 5 = 20, ¿cuánto vale x?", "pistas_dadas": 1},
        },
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"texto", "pista", "anotaciones", "proveedor"}
    assert isinstance(cuerpo["anotaciones"], list)


def test_basta_con_el_mensaje():
    assert cliente.post("/api/chat", json={"mensaje": "hola"}).status_code == 200


def test_basta_con_una_foto():
    assert cliente.post("/api/chat", json={"imagen_base64": "aGVsbG8="}).status_code == 200


def test_rechaza_mensaje_vacio_sin_foto():
    assert cliente.post("/api/chat", json={"mensaje": "   "}).status_code == 422


def test_las_pistas_no_tienen_tope_de_tres():
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
