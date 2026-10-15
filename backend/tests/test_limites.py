"""Pruebas del límite diario de mensajes, por sesión y por conexión."""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Configuracion
from app.datos.db import Sesion, Uso, sesion_bd
from app.main import app
from app.servicios import limites

cliente = TestClient(app)
RESPUESTA = {"texto": "¿Qué te piden?", "pista": None, "anotaciones": []}


@pytest.fixture
def config(monkeypatch):
    """Límites chicos para las pruebas: 3 por sesión y 5 por conexión."""
    valores = Configuracion(limite_mensajes_sesion=3, limite_mensajes_conexion=5, secreto_huellas="secreto-de-prueba")
    monkeypatch.setattr(limites, "obtener_configuracion", lambda: valores)
    limites._secreto.cache_clear()
    yield valores
    limites._secreto.cache_clear()


def nueva_sesion(nombre: str) -> str:
    with sesion_bd() as bd:
        bd.add(Sesion(id=nombre))
    return nombre


# ---------- La fecha y la huella ----------


def test_el_dia_se_cuenta_en_hora_de_costa_rica():
    # 03:00 UTC del 15 es todavía 21:00 del 14 en Costa Rica.
    assert limites.hoy(datetime.datetime(2026, 10, 15, 3, 0, tzinfo=datetime.UTC)) == datetime.date(2026, 10, 14)
    assert limites.hoy(datetime.datetime(2026, 10, 15, 6, 0, tzinfo=datetime.UTC)) == datetime.date(2026, 10, 15)


def test_la_huella_no_contiene_la_ip_y_cambia_cada_dia(config):
    ip, dia = "190.10.20.30", datetime.date(2026, 10, 14)
    huella = limites.huella_de_conexion(ip, dia)
    assert ip not in huella and "190" not in huella
    assert huella == limites.huella_de_conexion(ip, dia)  # mismo día, misma huella
    assert huella != limites.huella_de_conexion(ip, dia + datetime.timedelta(days=1))
    assert huella != limites.huella_de_conexion("190.10.20.31", dia)


def test_la_huella_depende_del_secreto(config, monkeypatch):
    dia = datetime.date(2026, 10, 14)
    antes = limites.huella_de_conexion("1.2.3.4", dia)
    monkeypatch.setattr(limites, "obtener_configuracion", lambda: Configuracion(secreto_huellas="otro"))
    limites._secreto.cache_clear()
    assert limites.huella_de_conexion("1.2.3.4", dia) != antes


# ---------- revisar y registrar ----------


def test_sin_sesion_o_con_una_que_no_existe(config):
    with pytest.raises(limites.SesionInvalida):
        limites.revisar(None, "1.1.1.1")
    with pytest.raises(limites.SesionInvalida):
        limites.revisar("no-existe", "1.1.1.1")


def test_la_sesion_llega_a_su_limite(config):
    s = nueva_sesion("ana")
    for restantes in (2, 1, 0):
        assert limites.revisar(s, "1.1.1.1").restantes == restantes + 1
        assert limites.registrar(s, "1.1.1.1").restantes == restantes
    with pytest.raises(limites.LimiteAlcanzado, match="Mañana podés seguir"):
        limites.revisar(s, "1.1.1.1")


def test_revisar_no_cuenta_nada(config):
    s = nueva_sesion("ana")
    for _ in range(10):
        limites.revisar(s, "1.1.1.1")
    with sesion_bd() as bd:
        assert bd.scalars(select(Uso)).all() == []


def test_al_dia_siguiente_vuelve_a_tener_cupo(config):
    s = nueva_sesion("ana")
    ayer = datetime.datetime(2026, 10, 14, 18, 0, tzinfo=datetime.UTC)
    for _ in range(3):
        limites.registrar(s, "1.1.1.1", ayer)
    with pytest.raises(limites.LimiteAlcanzado):
        limites.revisar(s, "1.1.1.1", ayer)
    assert limites.revisar(s, "1.1.1.1", ayer + datetime.timedelta(days=1)).restantes == 3


def test_una_conexion_compartida_tiene_su_propio_limite(config):
    # Un laboratorio: varios estudiantes, misma conexión. La conexión aguanta 5 en total.
    for i, estudiante in enumerate(["ana", "beto", "caro"]):
        nueva_sesion(estudiante)
    for estudiante in ["ana", "ana", "beto", "beto", "caro"]:
        limites.revisar(estudiante, "200.1.1.1")
        limites.registrar(estudiante, "200.1.1.1")
    with pytest.raises(limites.LimiteAlcanzado, match="desde esta conexión"):
        limites.revisar("caro", "200.1.1.1")
    # Desde otra conexión, caro todavía puede.
    assert limites.revisar("caro", "200.9.9.9").restantes == 2


def test_borrar_el_navegador_no_salta_el_limite_de_la_conexion(config):
    for i in range(5):
        s = nueva_sesion(f"sesion-{i}")  # cada vez una sesión nueva, como si borrara los datos
        limites.registrar(s, "200.1.1.1")
    with pytest.raises(limites.LimiteAlcanzado):
        limites.revisar(nueva_sesion("otra-mas"), "200.1.1.1")


def test_en_la_base_no_queda_ninguna_ip(config):
    s = nueva_sesion("ana")
    limites.registrar(s, "190.10.20.30")
    with sesion_bd() as bd:
        claves = [u.clave for u in bd.scalars(select(Uso))]
    assert len(claves) == 2
    assert not any("190" in c or "10.20.30" in c for c in claves)
    assert sorted(c.split(":")[0] for c in claves) == ["origen", "sesion"]


# ---------- La ruta /api/chat ----------


def test_la_ruta_pide_sesion(config, modelo):
    respuesta = cliente.post("/api/chat", json={"mensaje": "hola"})
    assert respuesta.status_code == 401
    assert "Recargá la página" in respuesta.json()["detail"]
    assert modelo.llamadas == []


def test_la_ruta_rechaza_una_sesion_inventada(config, modelo):
    assert cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": "inventada"}).status_code == 401


def test_la_ruta_cuenta_y_avisa_cuantos_quedan(config, modelo):
    s = nueva_sesion("ana")
    modelo.responde(RESPUESTA, RESPUESTA, RESPUESTA)
    restantes = [cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": s}).headers["x-mensajes-restantes"] for _ in range(3)]
    assert restantes == ["2", "1", "0"]
    cuarta = cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": s})
    assert cuarta.status_code == 429
    assert cuarta.json()["detail"] == limites.MENSAJE_LIMITE_SESION
    assert len(modelo.llamadas) == 3  # la cuarta ni siquiera llegó a la IA


def test_si_el_tutor_falla_el_mensaje_no_se_cuenta(config):
    # Sin proveedores (lo que pone conftest), la ruta responde 503 y no gasta cupo.
    s = nueva_sesion("ana")
    for _ in range(5):
        assert cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": s}).status_code == 503
    assert limites.revisar(s, "testclient").restantes == 3


def test_detras_de_un_proxy_usa_la_ip_reenviada(config, modelo, monkeypatch):
    monkeypatch.setattr(
        "app.rutas.chat.obtener_configuracion", lambda: Configuracion(confiar_en_proxy=True)
    )
    s = nueva_sesion("ana")
    modelo.responde(RESPUESTA)
    cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": s}, headers={"X-Forwarded-For": "190.1.2.3, 10.0.0.1"})
    huella = limites.huella_de_conexion("190.1.2.3", limites.hoy())
    with sesion_bd() as bd:
        assert bd.get(Uso, (f"origen:{huella}", limites.hoy())) is not None


def test_sin_confiar_en_el_proxy_ignora_la_ip_reenviada(config, modelo):
    s = nueva_sesion("ana")
    modelo.responde(RESPUESTA)
    cliente.post("/api/chat", json={"mensaje": "hola", "sesion_id": s}, headers={"X-Forwarded-For": "190.1.2.3"})
    huella_falsa = limites.huella_de_conexion("190.1.2.3", limites.hoy())
    with sesion_bd() as bd:
        assert bd.get(Uso, (f"origen:{huella_falsa}", limites.hoy())) is None
