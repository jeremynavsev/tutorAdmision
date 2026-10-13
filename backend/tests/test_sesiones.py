"""Pruebas de POST /api/sesiones."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.datos.db import Sesion, sesion_bd
from app.main import app

cliente = TestClient(app)


def test_crea_una_sesion_anonima_y_la_guarda():
    respuesta = cliente.post("/api/sesiones", json={"acepto_aviso": True})
    assert respuesta.status_code == 201
    sesion_id = respuesta.json()["sesion_id"]
    assert str(uuid.UUID(sesion_id)) == sesion_id  # es un UUID válido
    with sesion_bd() as bd:
        assert bd.get(Sesion, sesion_id) is not None


def test_cada_sesion_tiene_un_id_distinto():
    ids = {cliente.post("/api/sesiones", json={"acepto_aviso": True}).json()["sesion_id"] for _ in range(20)}
    assert len(ids) == 20


def test_sin_aceptar_el_aviso_no_hay_sesion():
    respuesta = cliente.post("/api/sesiones", json={"acepto_aviso": False})
    assert respuesta.status_code == 400
    assert "aceptar el aviso" in respuesta.json()["detail"]
    with sesion_bd() as bd:
        assert bd.scalars(select(Sesion)).all() == []


def test_falta_el_campo_del_aviso():
    assert cliente.post("/api/sesiones", json={}).status_code == 422


def test_la_respuesta_solo_trae_el_id():
    assert set(cliente.post("/api/sesiones", json={"acepto_aviso": True}).json()) == {"sesion_id"}
