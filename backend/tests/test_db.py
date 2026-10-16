"""Pruebas de la base de datos: conexión, tablas y transacciones."""

import datetime

import pytest
from sqlalchemy import inspect, select

from app.datos import db
from app.datos.db import Sesion, Uso, _normalizar_url, sesion_bd


def test_crea_las_tablas():
    with sesion_bd() as bd:
        tablas = set(inspect(bd.get_bind()).get_table_names())
    assert {"sesiones", "uso"} <= tablas


def test_las_tablas_no_tienen_columnas_de_datos_personales():
    # Si alguien agrega una columna aquí, que sea a propósito y pensando en la privacidad.
    assert {c.name for c in Sesion.__table__.columns} == {"id", "creada"}
    assert {c.name for c in Uso.__table__.columns} == {"clave", "dia", "mensajes"}


def test_guarda_y_lee_una_sesion():
    with sesion_bd() as bd:
        bd.add(Sesion(id="abc"))
    with sesion_bd() as bd:
        sesion = bd.get(Sesion, "abc")
        assert sesion is not None and sesion.creada.year >= 2026


def test_el_uso_se_cuenta_por_clave_y_dia():
    hoy, ayer = datetime.date(2026, 10, 13), datetime.date(2026, 10, 12)
    with sesion_bd() as bd:
        bd.add_all([Uso(clave="sesion:abc", dia=hoy, mensajes=3), Uso(clave="sesion:abc", dia=ayer, mensajes=40)])
    with sesion_bd() as bd:
        assert bd.get(Uso, ("sesion:abc", hoy)).mensajes == 3
        assert bd.get(Uso, ("sesion:abc", ayer)).mensajes == 40


def test_si_algo_falla_no_se_guarda_nada():
    with pytest.raises(RuntimeError):
        with sesion_bd() as bd:
            bd.add(Sesion(id="a-medias"))
            raise RuntimeError("falló a media transacción")
    with sesion_bd() as bd:
        assert bd.scalars(select(Sesion)).all() == []


def test_cada_prueba_empieza_con_la_base_vacia():
    with sesion_bd() as bd:
        assert bd.scalars(select(Sesion)).all() == []
        assert bd.scalars(select(Uso)).all() == []


@pytest.mark.parametrize(
    "url, esperado",
    [
        ("postgres://u:c@host/maestro", "postgresql+psycopg://u:c@host/maestro"),
        ("postgresql://u:c@host/maestro?sslmode=require", "postgresql+psycopg://u:c@host/maestro?sslmode=require"),
        ("postgresql+psycopg://u:c@host/maestro", "postgresql+psycopg://u:c@host/maestro"),
        ("sqlite:///./maestro.db", "sqlite:///./maestro.db"),
    ],
)
def test_acepta_las_urls_de_neon(url, esperado):
    assert _normalizar_url(url) == esperado


def test_funciona_con_un_archivo_sqlite(tmp_path):
    archivo = tmp_path / "prueba.db"
    db.configurar(f"sqlite:///{archivo}")
    with sesion_bd() as bd:
        bd.add(Sesion(id="en-disco"))
    db.configurar(f"sqlite:///{archivo}")  # como si el servidor se reiniciara
    with sesion_bd() as bd:
        assert bd.get(Sesion, "en-disco") is not None
