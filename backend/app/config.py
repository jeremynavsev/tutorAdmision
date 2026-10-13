"""Configuración del backend.

Lee las variables de entorno y, si existe, el archivo ``backend/.env``, sin
dependencias extra: el .env se interpreta con un lector mínimo de líneas
``CLAVE=valor``. Las variables ya definidas en el entorno tienen prioridad.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent


def _cargar_env(ruta: Path) -> None:
    """Carga un archivo .env en ``os.environ`` sin pisar variables existentes."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave.strip(), valor)


def _entero(nombre: str, por_defecto: int) -> int:
    try:
        return int(os.environ.get(nombre, por_defecto))
    except ValueError:
        return por_defecto


def _decimal(nombre: str, por_defecto: float) -> float:
    try:
        return float(os.environ.get(nombre, por_defecto))
    except ValueError:
        return por_defecto


def _lista(nombre: str, por_defecto: tuple[str, ...]) -> tuple[str, ...]:
    """Lee una lista separada por comas. "ninguno" la deja vacía; sin valor, usa la de por defecto."""
    crudo = os.environ.get(nombre, "").strip()
    if not crudo:
        return por_defecto
    if crudo.lower() in ("ninguno", "ninguna", "no"):
        return ()
    return tuple(parte.strip() for parte in crudo.split(",") if parte.strip())


def _texto(nombre: str, por_defecto: str) -> str:
    """Lee una variable de texto; si está vacía, usa el valor por defecto."""
    return os.environ.get(nombre, "").strip() or por_defecto


@dataclass(frozen=True)
class Configuracion:
    """Valores de configuración de la aplicación."""

    gemini_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""
    gemini_modelo: str = "gemini-3.8-flash"
    groq_modelo: str = "openai/gpt-oss-120b"
    mistral_modelo: str = "mistral-small-latest"
    tiempo_maximo_ia: float = 30.0
    gemini_razonamiento: str = "low"
    orden_proveedores: tuple[str, ...] = ("groq", "gemini", "mistral")
    gemini_modelos_respaldo: tuple[str, ...] = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
    database_url: str = "sqlite:///./maestro.db"
    limite_mensajes_sesion: int = 40
    limite_mensajes_dia: int = 150
    origenes_permitidos: list[str] = field(default_factory=lambda: ["http://localhost:3100"])


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve la configuración, leyendo el .env una sola vez."""
    _cargar_env(RAIZ_BACKEND / ".env")
    origenes = os.environ.get("ORIGENES_PERMITIDOS", "http://localhost:3100")
    return Configuracion(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        mistral_api_key=os.environ.get("MISTRAL_API_KEY", ""),
        gemini_modelo=_texto("GEMINI_MODELO", Configuracion.gemini_modelo),
        groq_modelo=_texto("GROQ_MODELO", Configuracion.groq_modelo),
        mistral_modelo=_texto("MISTRAL_MODELO", Configuracion.mistral_modelo),
        tiempo_maximo_ia=_decimal("TIEMPO_MAXIMO_IA", Configuracion.tiempo_maximo_ia),
        gemini_razonamiento=_texto("GEMINI_RAZONAMIENTO", Configuracion.gemini_razonamiento).lower(),
        orden_proveedores=tuple(n.lower() for n in _lista("ORDEN_PROVEEDORES", Configuracion.orden_proveedores)),
        gemini_modelos_respaldo=_lista("GEMINI_MODELOS_RESPALDO", Configuracion.gemini_modelos_respaldo),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./maestro.db"),
        limite_mensajes_sesion=_entero("LIMITE_MENSAJES_SESION", 40),
        limite_mensajes_dia=_entero("LIMITE_MENSAJES_DIA", 150),
        origenes_permitidos=[o.strip() for o in origenes.split(",") if o.strip()],
    )
