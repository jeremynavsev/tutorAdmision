"""Modelos Pydantic de entrada y salida de la API."""

from typing import Literal

from pydantic import BaseModel, Field


class RespuestaOk(BaseModel):
    """Respuesta mínima de confirmación."""

    ok: bool = True


class Solucion(BaseModel):
    """Solución esperada de un ejercicio (no se envía al estudiante)."""

    tipo: Literal["opcion", "expresion", "numero"]
    valor: str


class Ejercicio(BaseModel):
    """Ejercicio del banco tal como se guarda en ``ejercicios/banco.json``."""

    id: str
    tema: str
    area: str
    enunciado: str
    opciones: list[str]
    solucion: Solucion
    pasos: list[str]
    errores_comunes: list[str]


class EjercicioPublico(BaseModel):
    """Ejercicio sin solución ni pasos: lo que ve el estudiante."""

    id: str
    tema: str
    area: str
    enunciado: str
    opciones: list[str]


class SesionEntrada(BaseModel):
    """Datos para abrir una sesión de práctica. No incluye datos personales."""

    acepto_aviso: bool
    ejercicio_id: str | None = None


class MensajeChat(BaseModel):
    """Un mensaje de la conversación."""

    rol: Literal["estudiante", "tutor"]
    texto: str


class ChatEntrada(BaseModel):
    """Mensaje del estudiante hacia el tutor."""

    sesion_id: str | None = None
    ejercicio_id: str | None = None
    mensaje: str = Field(min_length=1, max_length=2000)
    imagen_base64: str | None = None


class ChatSalida(BaseModel):
    """Respuesta del tutor."""

    respuesta: str
    es_pista: bool = False
    proveedor: str = "prueba"
