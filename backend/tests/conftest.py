"""Configuración común de las pruebas."""

import json

import pytest

from app.servicios import modelos_ia
from app.servicios.modelos_ia import RespuestaModelo, SinProveedores


@pytest.fixture(autouse=True)
def sin_proveedores_reales(monkeypatch):
    """Ninguna prueba llama a un proveedor de IA de verdad: ni internet ni cuota."""

    def sin_red(*args, **kwargs):
        raise SinProveedores(["prueba: no se llama a proveedores reales"])

    monkeypatch.setattr(modelos_ia, "completar", sin_red)


class ModeloFalso:
    """Hace de cadena de proveedores: devuelve, en orden, las respuestas que se le encolan."""

    def __init__(self):
        self.respuestas: list = []
        self.llamadas: list[list[dict]] = []

    def responde(self, *respuestas):
        """Encola respuestas: un dict (se manda como JSON), un texto crudo o una excepción."""
        self.respuestas.extend(respuestas)
        return self

    def __call__(self, mensajes, **kwargs):
        self.llamadas.append(mensajes)
        if not self.respuestas:
            raise AssertionError("El tutor pidió más respuestas de las que la prueba preparó.")
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        texto = siguiente if isinstance(siguiente, str) else json.dumps(siguiente, ensure_ascii=False)
        return RespuestaModelo(texto=texto, proveedor="falso", modelo="modelo-falso")


@pytest.fixture
def modelo(monkeypatch) -> ModeloFalso:
    """Reemplaza la cadena de proveedores por un modelo falso que la prueba controla."""
    falso = ModeloFalso()
    monkeypatch.setattr(modelos_ia, "completar", falso)
    return falso
