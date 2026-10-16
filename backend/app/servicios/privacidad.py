"""Detección de datos personales en lo que escribe el estudiante.

Antes de mandarle un mensaje a la IA se ocultan las cédulas, los teléfonos, los
correos y los nombres completos: se reemplazan por una marca como
``[cédula oculta]``. Así ese dato nunca llega al proveedor, aunque la página no
lo haya avisado antes.

Los ejercicios están llenos de números, así que se cuida de no confundirlos:

- siempre se detectan los formatos inconfundibles: cédula con guiones
  (1-2345-0678), teléfono con prefijo (+506 8888 8888) y correos;
- un teléfono sin prefijo (8888-8888) o un número suelto de 8 a 12 dígitos solo
  cuenta si viene cerca de palabras como "cédula", "teléfono", "cel",
  "WhatsApp" o "mi número". Así "4000-2000" en un ejercicio es una resta;
- el nombre completo, solo en frases como "me llamo Ana Rodríguez".

Las direcciones no se detectan: son demasiado variables. Para eso queda la regla
de las instrucciones del tutor.

El frontend tiene una copia de estas reglas (``web/lib/privacidad.ts``) para
avisarle al estudiante antes de enviar. Si cambian aquí, cambian allá.
"""

import re
from dataclasses import dataclass

MARCAS = {
    "cedula": "[cédula oculta]",
    "telefono": "[teléfono oculto]",
    "correo": "[correo oculto]",
    "nombre": "[nombre oculto]",
}

_LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
_MAYUSCULA = "A-ZÁÉÍÓÚÜÑ"

_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Cédula de identidad: 1-2345-0678 (o con espacios o puntos: 1 2345 0678).
_CEDULA = re.compile(r"(?<![\d-])[1-9][- .]\d{4}[- .]\d{4}(?![\d-])")
# Teléfono: 8888-8888, 8888 8888, +506 8888 8888, (506) 88888888.
_TELEFONO = re.compile(r"(?:(?:\+|\b00)?\(?506\)?[\s-]?)?(?<![\d-])[245678]\d{3}[\s-]\d{4}(?![\d-])")
_TELEFONO_CON_PREFIJO = re.compile(r"(?:\+|\b00)\(?506\)?[\s-]?[245678]\d{7}(?!\d)")
# Un número suelto de 8 a 12 dígitos (también DIMEX): solo si hay contexto.
_NUMERO_LARGO = re.compile(r"(?<![\d.,])\d{8,12}(?![\d.,])")
_CONTEXTO = re.compile(
    r"\b(c[ée]dula|c[ée]d\.?|identificaci[óo]n|dimex|tel[ée]fono|tel\.?|cel(?:ular)?|whats?app|mi\s+n[úu]mero|n[úu]mero\s+(?:de\s+)?(?:tel|cel|c[ée]d)|ll[áa]mame|escribime)\b",
    re.IGNORECASE,
)
_PALABRAS_DE_TELEFONO = ("tel", "cel", "whats", "llam", "escrib", "mi n")


def _contexto_antes(texto: str, inicio: int) -> str | None:
    """La palabra de contexto ("cédula", "cel"…) más cercana en los 40 caracteres anteriores, si hay.

    La más cercana manda: en "mi número de cédula es …" el número es una cédula.
    """
    hallados = list(_CONTEXTO.finditer(texto[max(0, inicio - 40) : inicio]))
    return hallados[-1].group(0).lower() if hallados else None
# Nombre completo: "me llamo Ana Rodríguez", "mi nombre es Ana María Rodríguez Mora".
_NOMBRE = re.compile(
    rf"\b(?:me\s+llamo|mi\s+nombre\s+es|soy)\s+((?:[{_MAYUSCULA}][{_LETRA}]+)(?:\s+(?:de\s+(?:la\s+)?)?[{_MAYUSCULA}][{_LETRA}]+){{1,4}})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Hallazgo:
    tipo: str
    inicio: int
    fin: int


def _parece_nombre(texto: str) -> bool:
    """Dos o más palabras con mayúscula inicial, sin contar "de" y "la" en medio."""
    palabras = texto.split()
    if not palabras or not palabras[0][0].isupper():
        return False  # "soy de Pérez Zeledón": empieza con "de", no es un nombre
    nombres = [p for p in palabras if p.lower() not in ("de", "la")]
    return len(nombres) >= 2 and all(p[0].isupper() for p in nombres)


def encontrar(texto: str) -> list[Hallazgo]:
    """Los datos personales del texto, en orden y sin superponerse."""
    hallazgos = [Hallazgo("correo", m.start(), m.end()) for m in _CORREO.finditer(texto)]
    hallazgos += [Hallazgo("cedula", m.start(), m.end()) for m in _CEDULA.finditer(texto)]
    hallazgos += [Hallazgo("telefono", m.start(), m.end()) for m in _TELEFONO_CON_PREFIJO.finditer(texto)]
    for m in _TELEFONO.finditer(texto):
        # Con prefijo +506 siempre; sin prefijo, solo si hay una palabra de teléfono cerca.
        if "506" in m.group(0) or _contexto_antes(texto, m.start()):
            hallazgos.append(Hallazgo("telefono", m.start(), m.end()))

    for m in _NUMERO_LARGO.finditer(texto):
        palabra = _contexto_antes(texto, m.start())
        if palabra:
            es_telefono = any(p in palabra for p in _PALABRAS_DE_TELEFONO)
            hallazgos.append(Hallazgo("telefono" if es_telefono else "cedula", m.start(), m.end()))

    for m in _NOMBRE.finditer(texto):
        if _parece_nombre(m.group(1)):
            hallazgos.append(Hallazgo("nombre", m.start(1), m.end(1)))

    # Sin superposiciones: gana el que empieza antes (y, si empatan, el más largo).
    hallazgos.sort(key=lambda h: (h.inicio, -(h.fin - h.inicio)))
    limpios: list[Hallazgo] = []
    for h in hallazgos:
        if not limpios or h.inicio >= limpios[-1].fin:
            limpios.append(h)
    return limpios


_NOMBRES_LEGIBLES = {"cedula": "la cédula", "telefono": "el teléfono", "correo": "el correo", "nombre": "el nombre completo"}


def aviso_de_datos_ocultos(tipos: list[str]) -> str:
    """Texto para el estudiante cuando se le quitaron datos personales del mensaje."""
    unicos = list(dict.fromkeys(_NOMBRES_LEGIBLES[t] for t in tipos))
    lista = unicos[0] if len(unicos) == 1 else ", ".join(unicos[:-1]) + " y " + unicos[-1]
    return f"Ojo: quité {lista} de tu mensaje, porque para practicar no hace falta compartir datos personales."


def ocultar(texto: str) -> tuple[str, list[str]]:
    """Reemplaza los datos personales por marcas. Devuelve el texto y los tipos que se ocultaron."""
    hallazgos = encontrar(texto)
    if not hallazgos:
        return texto, []
    partes, ultimo = [], 0
    for h in hallazgos:
        partes += [texto[ultimo : h.inicio], MARCAS[h.tipo]]
        ultimo = h.fin
    partes.append(texto[ultimo:])
    return "".join(partes), [h.tipo for h in hallazgos]
