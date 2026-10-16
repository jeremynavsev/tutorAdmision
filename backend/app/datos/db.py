"""Conexión a la base de datos y tablas, con SQLAlchemy.

En local se usa SQLite (``sqlite:///./maestro.db``); en producción, PostgreSQL
en Neon con el controlador ``psycopg``. La URL sale de ``DATABASE_URL``.

Por privacidad no se guarda ningún dato personal:

- ``Sesion`` es un identificador al azar con su fecha de creación. No sabe
  quién es el estudiante.
- ``Uso`` cuenta mensajes por día. Su clave es una sesión o la huella de una
  conexión; la huella es un resumen irreversible de la IP que cambia cada día,
  así que nunca queda guardada una IP.

El contenido de las conversaciones no se guarda aquí: vive en el navegador del
estudiante.
"""

import datetime
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Date, DateTime, Engine, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    """Base de todas las tablas."""


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class Sesion(Base):
    """Sesión anónima de práctica: se crea cuando el estudiante acepta el aviso de entrada."""

    __tablename__ = "sesiones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    creada: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Uso(Base):
    """Cuántos mensajes se mandaron en un día, por sesión o por conexión."""

    __tablename__ = "uso"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    """``sesion:<id>`` o ``origen:<huella del día>``."""

    dia: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    mensajes: Mapped[int] = mapped_column(Integer, default=0)


def _normalizar_url(url: str) -> str:
    """Neon entrega ``postgres://`` o ``postgresql://``; SQLAlchemy necesita que se nombre el controlador."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo) :]
    return url


def crear_motor(url: str) -> Engine:
    """Crea el motor de SQLAlchemy para la URL dada."""
    url = _normalizar_url(url)
    if url.startswith("sqlite"):
        opciones: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # En memoria (pruebas): una sola conexión compartida, o cada una vería una base vacía.
            opciones["poolclass"] = StaticPool
        return create_engine(url, **opciones)
    # pool_pre_ping: Neon cierra las conexiones inactivas; así se detecta antes de usarlas.
    return create_engine(url, pool_pre_ping=True)


_motor: Engine | None = None
_fabrica: sessionmaker[Session] | None = None


def configurar(url: str | None = None) -> Engine:
    """Conecta la base de datos y crea las tablas que falten. Sin URL, usa la de la configuración."""
    global _motor, _fabrica
    if _motor is not None:
        _motor.dispose()
    _motor = crear_motor(url or obtener_configuracion().database_url)
    _fabrica = sessionmaker(_motor, expire_on_commit=False)
    Base.metadata.create_all(_motor)
    return _motor


@contextmanager
def sesion_bd() -> Iterator[Session]:
    """Abre una transacción: confirma al salir bien y deshace todo si hay un error."""
    if _fabrica is None:
        configurar()
    assert _fabrica is not None
    with _fabrica.begin() as sesion:
        yield sesion
