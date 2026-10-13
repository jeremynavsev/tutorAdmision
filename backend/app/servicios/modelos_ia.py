"""Cadena de proveedores de IA: Gemini → Groq → Mistral.

Los tres ofrecen una API compatible con la de OpenAI, así que se usa el mismo
cliente ``openai`` con otra URL base. Se prueban en orden y, si uno falla
(error, tiempo agotado, cuota llena, modelo retirado o respuesta vacía), se pasa
al siguiente. Solo entran los proveedores que tienen llave en el ``.env``.

Si el mensaje trae una foto, se saltan los proveedores cuyo modelo no lee
imágenes.

Por privacidad, los registros (logs) dicen qué proveedor falló y por qué, pero
nunca el contenido de los mensajes.

Para revisar las llaves desde la terminal:
    python -m app.servicios.modelos_ia
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import openai
from openai import OpenAI

from app.config import Configuracion, obtener_configuracion

registro = logging.getLogger(__name__)

Mensajes = list[dict]


@dataclass(frozen=True)
class Proveedor:
    """Datos de conexión de un proveedor compatible con la API de OpenAI."""

    nombre: str
    url_base: str
    modelo: str
    llave: str
    acepta_imagenes: bool
    extras: dict = field(default_factory=dict)
    """Parámetros propios del proveedor que se mandan en cada consulta."""


@dataclass(frozen=True)
class RespuestaModelo:
    """Lo que devolvió el modelo y quién lo devolvió."""

    texto: str
    proveedor: str
    modelo: str


class SinProveedores(Exception):
    """Ningún proveedor pudo responder. ``fallos`` dice qué le pasó a cada uno."""

    def __init__(self, fallos: list[str]):
        self.fallos = fallos
        detalle = "; ".join(fallos) if fallos else "no hay ninguna llave configurada"
        super().__init__(f"Ningún proveedor de IA respondió ({detalle}).")


def proveedores_disponibles(config: Configuracion | None = None) -> list[Proveedor]:
    """Lista los proveedores con llave configurada, en orden de prioridad."""
    c = config or obtener_configuracion()
    # Con poco razonamiento Gemini responde mucho más rápido; "normal" deja el valor del modelo.
    razonamiento = {} if c.gemini_razonamiento in ("", "normal") else {"reasoning_effort": c.gemini_razonamiento}
    candidatos = [
        Proveedor(
            nombre="gemini",
            url_base="https://generativelanguage.googleapis.com/v1beta/openai/",
            modelo=c.gemini_modelo,
            llave=c.gemini_api_key,
            acepta_imagenes=True,
            extras=razonamiento,
        ),
        Proveedor(
            nombre="groq",
            url_base="https://api.groq.com/openai/v1",
            modelo=c.groq_modelo,
            llave=c.groq_api_key,
            acepta_imagenes=False,
        ),
        Proveedor(
            nombre="mistral",
            url_base="https://api.mistral.ai/v1",
            modelo=c.mistral_modelo,
            llave=c.mistral_api_key,
            acepta_imagenes=True,
        ),
    ]
    return [p for p in candidatos if p.llave]


def _crear_cliente(proveedor: Proveedor, tiempo_maximo: float) -> OpenAI:
    # Sin reintentos propios: si falla, el "reintento" es pasar al siguiente proveedor.
    return OpenAI(api_key=proveedor.llave, base_url=proveedor.url_base, timeout=tiempo_maximo, max_retries=0)


def _trae_imagen(mensajes: Mensajes) -> bool:
    for mensaje in mensajes:
        contenido = mensaje.get("content")
        if isinstance(contenido, list) and any(parte.get("type") == "image_url" for parte in contenido):
            return True
    return False


def _describir_error(error: Exception) -> str:
    """Resumen corto del error, sin datos del mensaje."""
    if isinstance(error, openai.APITimeoutError):
        return "tiempo agotado"
    if isinstance(error, openai.APIConnectionError):
        return "sin conexión"
    if isinstance(error, openai.APIStatusError):
        return f"HTTP {error.status_code}"
    return type(error).__name__


def completar(
    mensajes: Mensajes,
    *,
    json: bool = True,
    proveedores: list[Proveedor] | None = None,
    tiempo_maximo: float | None = None,
    crear_cliente: Callable[[Proveedor, float], OpenAI] = _crear_cliente,
) -> RespuestaModelo:
    """Pide una respuesta a la cadena de proveedores.

    ``json=True`` pide al modelo que responda solo con un objeto JSON. Lanza
    ``SinProveedores`` si ninguno pudo responder.
    """
    lista = proveedores if proveedores is not None else proveedores_disponibles()
    espera = tiempo_maximo if tiempo_maximo is not None else obtener_configuracion().tiempo_maximo_ia
    con_imagen = _trae_imagen(mensajes)
    fallos: list[str] = []

    for proveedor in lista:
        if con_imagen and not proveedor.acepta_imagenes:
            fallos.append(f"{proveedor.nombre}: no lee imágenes")
            continue
        formato = {"response_format": {"type": "json_object"}} if json else {}
        try:
            cliente = crear_cliente(proveedor, espera)
            try:
                respuesta = cliente.chat.completions.create(
                    model=proveedor.modelo, messages=mensajes, **formato, **proveedor.extras
                )
            except openai.BadRequestError:
                # El proveedor no aceptó sus parámetros propios: se intenta sin ellos antes de rendirse.
                if not proveedor.extras:
                    raise
                registro.warning("Proveedor %s no aceptó %s; se reintenta sin eso.", proveedor.nombre, sorted(proveedor.extras))
                respuesta = cliente.chat.completions.create(model=proveedor.modelo, messages=mensajes, **formato)
            texto = (respuesta.choices[0].message.content or "").strip() if respuesta.choices else ""
        except Exception as error:  # cualquier fallo de un proveedor: se prueba el siguiente
            motivo = _describir_error(error)
            registro.warning("Proveedor %s (%s) falló: %s", proveedor.nombre, proveedor.modelo, motivo)
            fallos.append(f"{proveedor.nombre}: {motivo}")
            continue
        if not texto:
            registro.warning("Proveedor %s (%s) devolvió una respuesta vacía", proveedor.nombre, proveedor.modelo)
            fallos.append(f"{proveedor.nombre}: respuesta vacía")
            continue
        return RespuestaModelo(texto=texto, proveedor=proveedor.nombre, modelo=proveedor.modelo)

    raise SinProveedores(fallos)


def _revisar_llaves() -> None:
    """Prueba cada proveedor configurado por separado e informa si responde."""
    lista = proveedores_disponibles()
    if not lista:
        print("No hay llaves configuradas en backend/.env.")
        return
    mensajes = [{"role": "user", "content": 'Respondé solo con este JSON: {"ok": true}'}]
    for proveedor in lista:
        try:
            r = completar(mensajes, proveedores=[proveedor])
            print(f"✓ {proveedor.nombre} ({r.modelo}) responde")
        except SinProveedores as error:
            print(f"✗ {proveedor.nombre} ({proveedor.modelo}): {error.fallos[0]}")


if __name__ == "__main__":
    _revisar_llaves()
