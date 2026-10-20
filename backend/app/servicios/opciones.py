"""Control de que el tutor no señale una opción con sus palabras.

En los ejercicios de lectura, el tutor tiende a describir la opción correcta
("fijate en la frase que menciona una explicación natural y terrestre") en vez de
dejar que el estudiante haga la conexión entre el texto y las opciones. Las
instrucciones lo prohíben, pero la evaluación mostró que no alcanza. Este control
lo revisa en el código.

Las palabras "propias" de una opción son las que aparecen en esa opción y en
ninguna otra, ni en el texto del ejercicio: en "C) Lee con un propósito", con el
texto "el buen lector no es el que lee muchos libros…", la palabra propia es
"propósito". Si el tutor usa las palabras propias de una opción (2, o la única que
tenga), la está señalando.

- Si el ejercicio es del banco, se conoce la clave y solo se vigila la opción
  correcta: nombrar una opción incorrecta para descartarla no regala nada.
- Si no es del banco, se vigilan todas las opciones, porque no se sabe cuál es la
  correcta.

En los dos casos, si el estudiante ya mencionó esa opción (por su letra o con sus
palabras), el tutor puede hablar de ella: para explicarle por qué está bien o mal.

Este control no atrapa las paráfrasis con sinónimos ("contraste en la confianza"):
para eso haría falta otra consulta a la IA en cada mensaje.
"""

import re

from app.esquemas import AnotacionApunte, AnotacionEnunciado, ChatEntrada, ChatSalida
from app.servicios.buscador import opciones_del_texto, palabras
from app.servicios.verificador import _menciona_la_letra, _raiz, es_el_problema

LETRAS = "ABCDEFGH"
PALABRAS_PARA_SEÑALAR = 2
"""Cuántas palabras propias de una opción hacen falta para decir que el tutor la señala
(o todas, si la opción tiene menos)."""

_MARCA_DE_OPCION = re.compile(r"(?:^|(?<=\s))\(?[A-E]\)", re.MULTILINE)
_SOLO_LA_LETRA = re.compile(r"^\W*(?:(?:es\s+)?(?:la|opci[oó]n)\s+)?\(?([A-Ha-h])\)?\W*$", re.IGNORECASE)


LARGO_DE_RAIZ = 7
"""Se comparan los primeros 7 caracteres: así "memoriza", "memorizar" y "memorizó" son la
misma palabra, pero "contraste" y "contrario" no."""


def _raices(texto: str) -> set[str]:
    """Las palabras que cuentan, en una forma común para sus variantes, sin números."""
    return {_raiz(p)[:LARGO_DE_RAIZ] for p in palabras(texto) if not p.isdigit()}


def separar(problema: str) -> tuple[str, list[str]]:
    """El texto del ejercicio y sus opciones, si el problema las trae ("… A) 9 B) 10")."""
    opciones = opciones_del_texto(problema)
    if not opciones:
        return problema, []
    primera = _MARCA_DE_OPCION.search(problema)
    return (problema[: primera.start()] if primera else problema), opciones


def palabras_propias(enunciado: str, opciones: list[str]) -> list[set[str]]:
    """Para cada opción, las palabras que solo están en ella (ni en el texto ni en otra opción)."""
    del_texto = _raices(enunciado)
    de_cada_una = [_raices(o) for o in opciones]
    propias = []
    for i, raices in enumerate(de_cada_una):
        de_las_otras = set().union(*(r for j, r in enumerate(de_cada_una) if j != i))
        propias.append(raices - del_texto - de_las_otras)
    return propias


def _mencionada_por_el_estudiante(letra: str, propias: set[str], dichos: list[str]) -> bool:
    for dicho in dichos:
        if es_el_problema(dicho):
            continue  # el problema pegado trae todas las opciones: eso no es mencionarlas
        m = _SOLO_LA_LETRA.match(dicho)
        if (m and m.group(1).upper() == letra) or _menciona_la_letra(dicho, letra):
            return True
        if propias & _raices(dicho):
            return True
    return False


def opcion_senalada(
    salida: ChatSalida,
    entrada: ChatEntrada,
    enunciado: str | None = None,
    opciones: list[str] | None = None,
    clave: str | None = None,
) -> str | None:
    """La letra de la opción que el tutor señala con sus palabras, o None si no señala ninguna.

    ``enunciado``, ``opciones`` y ``clave`` vienen del banco si el ejercicio es de ahí. Si
    no, las opciones se sacan del problema de la pizarra o del que pegó el estudiante, y
    se vigilan todas.
    """
    if not opciones:
        problema = entrada.contexto.enunciado or next(
            (a.texto for a in salida.anotaciones if isinstance(a, AnotacionEnunciado)), None
        )
        dichos_con_problema = [m.texto for m in entrada.historial if m.autor == "estudiante"] + [entrada.mensaje]
        candidatos = [problema, *(d for d in dichos_con_problema if es_el_problema(d))]
        for texto in candidatos:
            if texto:
                enunciado, opciones = separar(texto)
                if opciones:
                    break
        if not opciones:
            return None
        clave = None  # fuera del banco no se sabe cuál es la correcta
    assert enunciado is not None

    propias = palabras_propias(enunciado, opciones)
    vigiladas = [LETRAS.index(clave)] if clave and clave in LETRAS[: len(opciones)] else range(len(opciones))
    dichos = [m.texto for m in entrada.historial if m.autor == "estudiante"] + [entrada.mensaje]
    del_tutor = _raices(" ".join([salida.texto, *(a.texto for a in salida.anotaciones if isinstance(a, AnotacionApunte))]))

    for i in vigiladas:
        if not propias[i]:
            continue
        usadas = propias[i] & del_tutor
        if len(usadas) >= min(PALABRAS_PARA_SEÑALAR, len(propias[i])):
            letra = LETRAS[i]
            if not _mencionada_por_el_estudiante(letra, propias[i], dichos):
                return letra
    return None
