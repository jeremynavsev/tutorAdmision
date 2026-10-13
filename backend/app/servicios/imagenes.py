"""Limpieza y reducción de fotos con Pillow.

Antes de mandarle una foto a un proveedor de IA:

- se le quitan los metadatos (EXIF), que en fotos de celular pueden traer la
  ubicación GPS de donde se tomó;
- se corrige la orientación (muchas fotos llegan de lado);
- se reduce a un tamaño razonable y se guarda como JPEG, para ahorrar datos y
  cuota.

Solo se aceptan JPEG, PNG y WebP. Lo que no sea una imagen válida se rechaza
con ``ImagenInvalida`` y un mensaje que se le puede mostrar al estudiante.
"""

import base64
import binascii
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

LADO_MAXIMO_PX = 1600
CALIDAD_JPEG = 82
FORMATOS_ACEPTADOS = {"JPEG", "PNG", "WEBP"}
# Tope de pixeles al abrir: una foto de celular ronda los 12–50 megapixeles.
# Protege de imágenes hechas para agotar la memoria al descomprimirlas.
MAX_PIXELES = 60_000_000


class ImagenInvalida(Exception):
    """La foto no se puede usar. El mensaje está pensado para mostrárselo al estudiante."""


def _decodificar(imagen_base64: str) -> bytes:
    """Pasa de base64 a bytes; acepta que venga con el prefijo ``data:image/...;base64,``."""
    texto = imagen_base64.strip()
    if texto.startswith("data:"):
        texto = texto.partition(",")[2]
    try:
        datos = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        raise ImagenInvalida("No se pudo leer la foto. Probá tomarla de nuevo.") from None
    if not datos:
        raise ImagenInvalida("La foto llegó vacía. Probá tomarla de nuevo.")
    return datos


def limpiar_y_reducir(imagen_base64: str) -> str:
    """Devuelve la imagen en base64 como JPEG reducido, derecho y sin metadatos."""
    datos = _decodificar(imagen_base64)
    try:
        with warnings.catch_warnings():
            # Pillow solo avisa cuando una imagen es sospechosamente grande; aquí se trata como error.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            imagen = Image.open(io.BytesIO(datos))
            if imagen.format not in FORMATOS_ACEPTADOS:
                raise ImagenInvalida("Ese tipo de archivo no sirve. Mandá la foto en JPG o PNG.")
            if imagen.width * imagen.height > MAX_PIXELES:
                raise ImagenInvalida("La foto es demasiado grande. Probá con una de menor resolución.")
            imagen.load()
    except ImagenInvalida:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImagenInvalida("La foto es demasiado grande. Probá con una de menor resolución.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImagenInvalida("El archivo no es una imagen válida. Probá tomar la foto de nuevo.") from None

    # Gira la imagen según la orientación que guardó la cámara.
    imagen = ImageOps.exif_transpose(imagen)

    # JPEG no tiene transparencia: lo transparente pasa a blanco, como una hoja.
    if imagen.mode in ("RGBA", "LA", "P"):
        con_alfa = imagen.convert("RGBA")
        fondo = Image.new("RGB", con_alfa.size, "white")
        fondo.paste(con_alfa, mask=con_alfa.getchannel("A"))
        imagen = fondo
    else:
        imagen = imagen.convert("RGB")

    # Solo reduce; una foto pequeña no se agranda.
    imagen.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX), Image.Resampling.LANCZOS)

    # Se copian solo los pixeles a una imagen nueva: así no viaja ningún metadato.
    limpia = Image.new("RGB", imagen.size)
    limpia.paste(imagen)

    salida = io.BytesIO()
    limpia.save(salida, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return base64.b64encode(salida.getvalue()).decode("ascii")
