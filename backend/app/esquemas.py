"""Modelos Pydantic de entrada y salida de la API."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class RespuestaOk(BaseModel):
    """Respuesta mínima de confirmación."""

    ok: bool = True


class Solucion(BaseModel):
    """Solución esperada de un ejercicio (no se envía al estudiante)."""

    tipo: Literal["opcion", "expresion", "numero"]
    valor: str


Area = Literal["Razonamiento matemático", "Razonamiento verbal"]
Universidad = Literal["UCR", "UNA", "TEC"]
Dificultad = Literal["baja", "media", "alta"]


class Ejercicio(BaseModel):
    """Ejercicio del banco. El banco real es privado (ver ``app/datos/banco.py``)."""

    id: str = Field(min_length=1)
    tema: str = Field(min_length=1)
    area: Area
    universidades: list[Universidad] = []
    """Exámenes en los que aparece este tipo de ejercicio. Vacía si todavía no se sabe."""
    dificultad: Dificultad | None = None
    enunciado: str = Field(min_length=1)
    opciones: list[str]
    """Las opciones en orden: la primera es la A, la segunda la B, etc."""
    solucion: Solucion
    pasos: list[str]
    errores_comunes: list[str]
    fuente: str | None = None
    """De dónde salió el ejercicio (documento e ítem), para poder revisarlo."""

    @model_validator(mode="after")
    def _la_clave_existe(self) -> "Ejercicio":
        if self.solucion.tipo == "opcion":
            letras = "ABCDEFGH"[: len(self.opciones)]
            # Una sola letra: el texto vacío "está contenido" en cualquier texto y pasaría.
            if not letras or len(self.solucion.valor) != 1 or self.solucion.valor not in letras:
                raise ValueError(f"La clave '{self.solucion.valor}' no es una de las opciones ({', '.join(letras) or 'no hay opciones'}).")
        return self


class SesionEntrada(BaseModel):
    """Datos para abrir una sesión anónima. No incluye datos personales."""

    acepto_aviso: bool


class SesionSalida(BaseModel):
    """La sesión recién creada. El id es al azar y no identifica a la persona."""

    sesion_id: str


# ---------- Contrato del tutor (POST /api/chat) ----------
#
# Es el mismo contrato que usa el tutor simulado del frontend
# (web/lib/contrato.ts). Si cambia aquí, cambia allá.

# Las pistas no tienen un número fijo: se adaptan al estudiante. El tope es solo de seguridad.
MAX_PISTAS = 20
NumeroPista = Annotated[int, Field(ge=1, le=MAX_PISTAS)]

MAX_MENSAJE = 2000
MAX_HISTORIAL = 40
# Una foto ya reducida en el navegador pesa bastante menos; esto es un tope de seguridad.
MAX_IMAGEN_BASE64 = 7_000_000


class MensajeHistorial(BaseModel):
    """Un mensaje anterior de la conversación, para que el tutor tenga contexto."""

    autor: Literal["estudiante", "tutor"]
    texto: str = Field(max_length=4000)
    pista: NumeroPista | None = None


class Contexto(BaseModel):
    """Lo que ya pasó en el chat y el tutor necesita saber."""

    enunciado: str | None = Field(default=None, max_length=MAX_MENSAJE)
    """Problema que ya está copiado en la pizarra, si hay."""

    pistas_dadas: int = Field(default=0, ge=0)


class ChatEntrada(BaseModel):
    """Mensaje del estudiante hacia el tutor: texto, foto o ambos."""

    sesion_id: str | None = None
    mensaje: str = Field(default="", max_length=MAX_MENSAJE)
    imagen_base64: str | None = Field(default=None, max_length=MAX_IMAGEN_BASE64)
    historial: list[MensajeHistorial] = Field(default_factory=list, max_length=MAX_HISTORIAL)
    contexto: Contexto = Field(default_factory=Contexto)

    @model_validator(mode="after")
    def _texto_o_foto(self) -> "ChatEntrada":
        if not self.mensaje.strip() and not self.imagen_base64:
            raise ValueError("El mensaje necesita texto o una foto.")
        return self


class AnotacionEnunciado(BaseModel):
    """Copia el problema en la pizarra."""

    tipo: Literal["enunciado"] = "enunciado"
    texto: str = Field(min_length=1, max_length=MAX_MENSAJE)


class AnotacionCirculo(BaseModel):
    """Encierra en un círculo un dato que aparece tal cual en el enunciado."""

    tipo: Literal["circulo"] = "circulo"
    dato: str = Field(min_length=1, max_length=60)


class AnotacionApunte(BaseModel):
    """Escribe una línea con tiza en la zona de apuntes."""

    tipo: Literal["apunte"] = "apunte"
    texto: str = Field(min_length=1, max_length=120)


Anotacion = Annotated[
    AnotacionEnunciado | AnotacionCirculo | AnotacionApunte,
    Field(discriminator="tipo"),
]


class ChatSalida(BaseModel):
    """Respuesta del tutor: el texto, si es pista y qué dibujar en la pizarra."""

    texto: str
    pista: NumeroPista | None = None
    anotaciones: list[Anotacion] = Field(default_factory=list)
    proveedor: str = "prueba"
