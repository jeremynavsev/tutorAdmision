"""Pruebas de la limpieza de fotos, con imágenes generadas (no se llama a ningún proveedor)."""

import base64
import io

import pytest
from PIL import Image

from app.servicios.imagenes import LADO_MAXIMO_PX, ImagenInvalida, limpiar_y_reducir

ETIQUETA_ORIENTACION = 0x0112
ETIQUETA_GPS = 0x8825


def a_base64(imagen: Image.Image, formato: str = "JPEG", **opciones) -> str:
    salida = io.BytesIO()
    imagen.save(salida, format=formato, **opciones)
    return base64.b64encode(salida.getvalue()).decode()


def abrir(resultado_base64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(resultado_base64)))


def foto_de_celular(ancho: int = 4000, alto: int = 3000, orientacion: int = 6) -> str:
    """JPEG con ubicación GPS y marcada como girada, como las de un celular."""
    exif = Image.Exif()
    exif[ETIQUETA_ORIENTACION] = orientacion
    exif[0x010F] = "MarcaDelCelular"
    exif[ETIQUETA_GPS] = {1: "N", 2: (9.0, 22.0, 30.0), 3: "W", 4: (83.0, 42.0, 10.0)}
    return a_base64(Image.new("RGB", (ancho, alto), "gray"), exif=exif)


def test_la_foto_de_prueba_si_trae_gps():
    """Confirma que la foto de entrada de verdad tiene los metadatos que se van a borrar."""
    exif = abrir(foto_de_celular()).getexif()
    assert exif.get_ifd(ETIQUETA_GPS) and exif[ETIQUETA_ORIENTACION] == 6


def test_borra_todos_los_metadatos_incluida_la_ubicacion():
    limpia = abrir(limpiar_y_reducir(foto_de_celular()))
    exif = limpia.getexif()
    assert len(exif) == 0
    assert not exif.get_ifd(ETIQUETA_GPS)
    assert "exif" not in limpia.info
    assert b"MarcaDelCelular" not in base64.b64decode(limpiar_y_reducir(foto_de_celular()))


def test_endereza_la_foto_girada():
    # 4000x3000 marcada como "girar 90°" debe quedar vertical.
    limpia = abrir(limpiar_y_reducir(foto_de_celular(4000, 3000, orientacion=6)))
    assert limpia.height > limpia.width


def test_reduce_al_lado_maximo_sin_deformar():
    limpia = abrir(limpiar_y_reducir(foto_de_celular(4000, 3000, orientacion=1)))
    assert max(limpia.size) == LADO_MAXIMO_PX
    assert limpia.size == (1600, 1200)


def test_no_agranda_una_foto_pequena():
    assert abrir(limpiar_y_reducir(a_base64(Image.new("RGB", (300, 200), "white")))).size == (300, 200)


def test_siempre_devuelve_jpeg_rgb():
    for formato, modo in (("PNG", "RGBA"), ("WEBP", "RGB"), ("PNG", "P"), ("PNG", "L")):
        limpia = abrir(limpiar_y_reducir(a_base64(Image.new(modo, (50, 40)), formato)))
        assert (limpia.format, limpia.mode) == ("JPEG", "RGB")


def test_lo_transparente_queda_blanco():
    transparente = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    r, g, b = abrir(limpiar_y_reducir(a_base64(transparente, "PNG"))).getpixel((10, 10))
    assert min(r, g, b) > 240


def test_acepta_el_prefijo_data():
    foto = "data:image/jpeg;base64," + a_base64(Image.new("RGB", (30, 30)))
    assert abrir(limpiar_y_reducir(foto)).size == (30, 30)


def test_el_resultado_pesa_mucho_menos():
    import random

    random.seed(1)
    ruido = Image.frombytes("RGB", (3000, 2000), random.randbytes(3000 * 2000 * 3))
    original = a_base64(ruido, quality=95)
    assert len(limpiar_y_reducir(original)) < len(original) / 2


@pytest.mark.parametrize(
    "malo",
    [
        "esto no es base64 !!!",
        "",
        base64.b64encode(b"hola, no soy una imagen").decode(),
        base64.b64encode(b"%PDF-1.7 documento").decode(),
    ],
)
def test_rechaza_lo_que_no_es_una_imagen(malo):
    with pytest.raises(ImagenInvalida):
        limpiar_y_reducir(malo)


def test_rechaza_formatos_que_no_se_aceptan():
    with pytest.raises(ImagenInvalida, match="JPG o PNG"):
        limpiar_y_reducir(a_base64(Image.new("RGB", (20, 20)), "GIF"))


def test_rechaza_imagenes_gigantes():
    # 9000 x 9000 = 81 megapixeles, por encima del tope.
    gigante = a_base64(Image.new("L", (9000, 9000)), "PNG")
    with pytest.raises(ImagenInvalida, match="demasiado grande"):
        limpiar_y_reducir(gigante)
