"""Limpieza y reducción de fotos con Pillow.

Las fotos del cuaderno del estudiante se decodifican, se les quitan los
metadatos (EXIF, ubicación), se corrige la orientación y se reducen de tamaño
y calidad para ahorrar datos y tokens antes de enviarlas al modelo.
"""

LADO_MAXIMO_PX = 1280
CALIDAD_JPEG = 80


def limpiar_y_reducir(imagen_base64: str) -> str:
    """Devuelve la imagen en base64 como JPEG reducido y sin metadatos."""
    raise NotImplementedError
