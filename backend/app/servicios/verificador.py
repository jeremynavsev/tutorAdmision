"""Verificación de respuestas con SymPy.

Revisa, antes de enviarla, que la respuesta del tutor no le regale al
estudiante el resultado final. Para eso necesita conocer ese resultado, que
puede salir de dos lugares:

- del banco de ejercicios, cuando el problema está ahí (``Solucion``);
- de calcularlo aquí mismo, cuando el enunciado trae una ecuación de una
  incógnita ("3x - 5 + 20 = 50") o una operación directa ("¿cuánto es
  6000 ÷ 40 000?").

Si no se conoce el resultado (la mayoría de los problemas en palabras), no se
puede verificar y la respuesta pasa: ahí la única protección son las
instrucciones del tutor.

Seguridad: SymPy evalúa como código el texto que se le da. Por eso nunca recibe
texto libre: antes se extrae solo lo que es matemática (números, una letra
suelta como incógnita y operadores) y se limita su tamaño.
"""

import re
from dataclasses import dataclass, field
from fractions import Fraction

import sympy
from sympy.parsing.sympy_parser import convert_xor, implicit_multiplication_application, parse_expr, standard_transformations

from app.datos.revision import valor_de_opcion
from app.esquemas import AnotacionApunte, AnotacionEnunciado, ChatEntrada, ChatSalida, Solucion

_LETRAS = "a-zñáéíóúü"
# Número como se escribe en Costa Rica: "40 000", "1.500", "0,15", "3,5".
_NUMERO = r"\d{1,3}(?:[  .]\d{3})+(?:,\d+)?(?!\d)|\d+(?:[.,]\d+)?"
# Una letra suelta es una incógnita; pegada a otras letras es una palabra.
_VARIABLE = rf"(?<![{_LETRAS}])[a-z](?![{_LETRAS}])"
# Cada trozo del texto se clasifica una sola vez (recorrido lineal, sin retrocesos).
_TROZO = re.compile(
    rf"(?P<num>{_NUMERO})|(?P<var>{_VARIABLE})|(?P<op>[()+\-−*/^·×÷])|(?P<igual>=)|(?P<espacio>\s+)|(?P<otro>.)",
    re.IGNORECASE | re.DOTALL,
)
# Letras sueltas que en español casi siempre son palabras ("20 y 30", "5 a 10").
_PALABRAS_DE_UNA_LETRA = set("aeouy")
_OPERACION = re.compile(r"cu[aá]nto\s+(?:es|da|vale|resulta)\s+", re.IGNORECASE)

_TRANSFORMACIONES = standard_transformations + (implicit_multiplication_application, convert_xor)
_MAX_EXPRESION = 80


@dataclass(frozen=True)
class Esperada:
    """La respuesta final de un problema, en las formas en que puede aparecer."""

    valores: list[Fraction] = field(default_factory=list)
    """Valores numéricos de la respuesta (una ecuación puede tener varios)."""

    es_porcentaje: bool = False
    """Si la respuesta es un porcentaje: 15 % también puede decirse 0,15."""

    letra: str | None = None
    """Letra de la opción correcta, si es de selección."""


# ---------- Lectura de números ----------


def _a_fraccion(texto: str) -> Fraction | None:
    """Convierte "40 000", "1.500", "0,15" o "3/20" en una fracción exacta."""
    t = texto.strip().replace(" ", " ")
    if "/" in t:
        partes = t.split("/")
        if len(partes) != 2:
            return None
        arriba, abajo = _a_fraccion(partes[0]), _a_fraccion(partes[1])
        return arriba / abajo if arriba is not None and abajo else None
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+(?:,\d+)?", t):  # miles con espacio o punto
        t = t.replace(" ", "").replace(".", "")
    try:
        return Fraction(t.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


_NUMERO_EN_TEXTO = re.compile(rf"(?<![\w,.])({_NUMERO})(\s?/\s?\d+)?\s*(%|por\s?ciento)?", re.IGNORECASE)
# Un "-" es signo negativo (y no una resta) cuando viene tras un "=", un paréntesis o una palabra como "es".
_ANTES_DE_UN_NEGATIVO = re.compile(r"(?:^|[=(,:]|\b(?:es|son|da|vale|queda|a)\b)\s*[-−]\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class _Hallado:
    valor: Fraction
    con_porcentaje: bool
    inicio: int
    fin: int


def _numeros(texto: str) -> list[_Hallado]:
    """Todos los números de un texto, con su posición y si llevan "%"."""
    hallados = []
    for c in _NUMERO_EN_TEXTO.finditer(texto):
        valor = _a_fraccion(c.group(1) + (c.group(2) or "").replace(" ", ""))
        if valor is None:
            continue
        if _ANTES_DE_UN_NEGATIVO.search(texto[max(0, c.start() - 12) : c.start()]):
            valor = -valor
        hallados.append(_Hallado(valor, bool(c.group(3)), c.start(), c.end()))
    return hallados


# ---------- Cálculo de la respuesta ----------


def _corridas_matematicas(texto: str) -> list[str]:
    """Separa del texto los tramos que son solo matemática (números, incógnitas, operadores y "=")."""
    corridas: list[str] = []
    actual: list[str] = []
    ultimo = ""  # tipo del último trozo que no era espacio
    hubo_espacio = False

    def cerrar():
        nonlocal actual, ultimo
        if actual:
            corridas.append("".join(actual).strip())
        actual, ultimo = [], ""

    for trozo in _TROZO.finditer(texto):
        tipo = trozo.lastgroup
        valor = trozo.group()
        if tipo == "espacio":
            hubo_espacio = True
            if actual:
                actual.append(" ")
            continue
        es_palabra = (
            tipo == "var"
            and valor.lower() in _PALABRAS_DE_UNA_LETRA
            and hubo_espacio
            and ultimo in ("num", "var")
        )
        if tipo == "otro" or es_palabra:
            cerrar()
        else:
            actual.append(valor)
            ultimo = tipo
        hubo_espacio = False
    cerrar()
    return [c for c in corridas if c]


def _a_sympy(expresion: str) -> sympy.Expr | None:
    """Pasa una expresión ya filtrada a SymPy. Devuelve None si no es segura o no se entiende."""
    texto = expresion.strip().lower().replace(" ", " ")
    texto = re.sub(r"(?<=\d)[ .](?=\d{3}(?!\d))", "", texto)  # quita separadores de miles
    texto = re.sub(r"(?<=\d),(?=\d)", ".", texto)  # coma decimal
    texto = texto.replace("−", "-").replace("×", "*").replace("·", "*").replace("÷", "/")
    if not texto or len(texto) > _MAX_EXPRESION:
        return None
    # Solo números, letras sueltas y operadores. Nada de nombres ni funciones.
    if not re.fullmatch(r"[0-9a-z+\-*/^(). ]+", texto) or re.search(r"[a-z]{2,}", texto.replace(" ", "")):
        return None
    # El punto solo vale como decimal entre dígitos, nunca para acceder a algo de una letra ("x.y").
    if re.search(r"[a-z)]\s*\.|\.\s*[a-z(]", texto):
        return None
    # Evita potencias enormes o encadenadas, que colgarían el cálculo.
    if texto.count("^") > 2 or re.search(r"\^\s*\(?\s*\d{3,}", texto) or re.search(r"\^[^+\-*/]*\^", texto):
        return None
    try:
        return parse_expr(texto, transformations=_TRANSFORMACIONES, evaluate=True)
    except Exception:  # cualquier texto que SymPy no entienda
        return None


def _como_fracciones(soluciones) -> list[Fraction]:
    fracciones = []
    for solucion in soluciones:
        if solucion.is_Rational:
            fracciones.append(Fraction(int(solucion.p), int(solucion.q)))
        elif solucion.is_real:
            fracciones.append(Fraction(float(solucion)).limit_denominator(10**9))
    return fracciones


def resolver_enunciado(enunciado: str) -> list[Fraction]:
    """Calcula la respuesta si el enunciado trae una ecuación de una incógnita o una operación directa.

    Devuelve una lista vacía cuando no se puede calcular.
    """
    for corrida in _corridas_matematicas(enunciado):
        if corrida.count("=") != 1:
            continue
        izquierda, derecha = corrida.split("=")
        lado_a, lado_b = _a_sympy(izquierda), _a_sympy(derecha)
        if lado_a is None or lado_b is None:
            continue
        incognitas = (lado_a - lado_b).free_symbols
        if len(incognitas) != 1:
            continue
        try:
            soluciones = sympy.solve(sympy.Eq(lado_a, lado_b), incognitas.pop())
        except Exception:
            continue
        fracciones = _como_fracciones(soluciones)
        if fracciones:
            return fracciones

    operacion = _OPERACION.search(enunciado)
    if operacion:
        corridas = _corridas_matematicas(enunciado[operacion.end() : operacion.end() + _MAX_EXPRESION])
        valor = _a_sympy(corridas[0]) if corridas and "=" not in corridas[0] else None
        # Una operación tiene al menos un operador: "¿cuánto es 5?" no es una pregunta de cálculo.
        if valor is not None and not valor.free_symbols and valor.is_real and re.search(r"[+\-−*/^·×÷]", corridas[0]):
            return _como_fracciones([sympy.nsimplify(valor)])
    return []


_PALABRAS_DE_UNIDAD = 2
"""Una opción con más palabras que esto es una frase, no un valor ("más de 40 bombillos defectuosos")."""


def _valor_de_la_opcion(opcion: str) -> Fraction | None:
    """El valor de una opción que es un número ("50 gapes", "3 000") o una cuenta ("65 + 16²").

    Si es una frase con un número adentro, no cuenta: el tutor puede hablar de ese
    número al analizar la opción sin estar dando la respuesta.
    """
    sin_numeros = re.sub(rf"{_NUMERO}|[()+\-−*/^·×÷²³.,  ]", " ", opcion)
    if len(re.findall(rf"[{_LETRAS}]+", sin_numeros, re.IGNORECASE)) > _PALABRAS_DE_UNIDAD:
        return None
    valor = valor_de_opcion(opcion)
    if valor is None or valor.free_symbols or not valor.is_rational:
        return None
    return Fraction(int(valor.p), int(valor.q))


def respuesta_esperada(
    enunciado: str | None, solucion: Solucion | None = None, opciones: list[str] | None = None
) -> Esperada | None:
    """La respuesta final: la del banco si existe; si no, la que se pueda calcular.

    Con las opciones del ejercicio, una clave de selección también se reconoce por
    su valor: si la C es "50 gapes", decir "50" es tan revelador como decir "la C".
    """
    if solucion is not None:
        valor = solucion.valor.strip()
        if solucion.tipo == "opcion" and re.fullmatch(r"[A-Ea-e]", valor):
            letra = valor.upper()
            indice = ord(letra) - ord("A")
            opcion = opciones[indice] if opciones and indice < len(opciones) else None
            valor_opcion = _valor_de_la_opcion(opcion) if opcion else None
            return Esperada(valores=[valor_opcion] if valor_opcion is not None else [], letra=letra)
        numeros = _numeros(valor)
        if numeros:
            return Esperada(valores=[numeros[0].valor], es_porcentaje=numeros[0].con_porcentaje)
        return None
    if enunciado:
        valores = resolver_enunciado(enunciado)
        if valores:
            return Esperada(valores=valores)
    return None


# ---------- Comparación ----------


def _decimales(valor: Fraction) -> int | None:
    """Cuántos decimales tiene un número escrito como decimal (None si no es un decimal exacto)."""
    for d in range(0, 7):
        if (10**d) % valor.denominator == 0:
            return d
    return None


def _coincide(hallado: _Hallado, esperada: Esperada) -> bool:
    valor = hallado.valor
    for objetivo in esperada.valores:
        candidatos = [objetivo]
        if esperada.es_porcentaje and not hallado.con_porcentaje:
            candidatos.append(objetivo / 100)  # 15 % también se dice 0,15
        elif hallado.con_porcentaje and not esperada.es_porcentaje:
            continue
        for candidato in candidatos:
            if valor == candidato:
                return True
            # Un decimal redondeado o cortado también cuenta: 35/3 escrito como "11,67" o "11,6".
            decimales = _decimales(valor)
            if decimales and _decimales(candidato) is None and abs(valor - candidato) < Fraction(1, 10**decimales):
                return True
    return False


def _menciona_la_letra(texto: str, letra: str) -> bool:
    patron = rf"\b(?:la|opci[oó]n|alternativa|inciso|respuesta(?:\s+es)?(?:\s+la)?)\s+\(?{letra}\)?(?![{_LETRAS}])"
    return bool(re.search(patron, texto, re.IGNORECASE))


_COMO_RESULTADO = re.compile(
    r"(?:=|\bes\b|\bson\b|\bda\b|\bvale\b|\bqueda\b|\bobten[eé]s\b|\bresultado\b[^.\d]{0,20}|\brespuesta\b[^.\d]{0,20})\s*:?\s*[-−]?\s*$",
    re.IGNORECASE,
)
_SIGUE_LA_CUENTA = re.compile(r"\s*[a-z+\-−*/×÷^]", re.IGNORECASE)


def revela_solucion(texto: str, esperada: Esperada, enunciado: str | None = None) -> bool:
    """Detecta si un texto contiene la respuesta final.

    Si el valor de la respuesta también aparece como dato del enunciado (la
    respuesta es 5 y el problema dice "3x + 5 = 20"), mencionarlo no es una
    filtración ("restá 5 a ambos lados"). Ahí solo cuenta cuando se presenta
    como resultado: "x = 5", "da 5", "la respuesta es 5".
    """
    if esperada.letra and _menciona_la_letra(texto, esperada.letra):
        return True
    datos_del_enunciado = {abs(h.valor) for h in _numeros(enunciado or "")}
    for hallado in _numeros(texto):
        if not _coincide(hallado, esperada):
            continue
        if abs(hallado.valor) not in datos_del_enunciado:
            return True
        es_resultado = _COMO_RESULTADO.search(texto[max(0, hallado.inicio - 40) : hallado.inicio])
        if es_resultado and not _SIGUE_LA_CUENTA.match(texto[hallado.fin : hallado.fin + 3]):
            return True
    return False


def es_equivalente(propuesta: str, esperada: Esperada) -> bool:
    """Indica si lo que propone el estudiante coincide con la respuesta ("15 %", "0,15", "la C", "x = 5")."""
    if esperada.letra and (_menciona_la_letra(propuesta, esperada.letra) or propuesta.strip().upper() == esperada.letra):
        return True
    return any(_coincide(hallado, esperada) for hallado in _numeros(propuesta))


def filtra_la_respuesta(
    salida: ChatSalida, entrada: ChatEntrada, solucion: Solucion | None = None, opciones: list[str] | None = None
) -> bool:
    """Indica si la respuesta del tutor le regala al estudiante el resultado final.

    No es filtración si el estudiante ya dijo la respuesta correcta (en este
    mensaje o antes): ahí el tutor puede confirmarla.
    """
    enunciado = entrada.contexto.enunciado or next(
        (a.texto for a in salida.anotaciones if isinstance(a, AnotacionEnunciado)), None
    )
    esperada = respuesta_esperada(enunciado, solucion, opciones)
    if esperada is None:
        return False

    # ¿El estudiante ya la dijo? Se usa la misma regla que para el tutor: un número que
    # también es dato del problema no cuenta, salvo que lo presente como resultado.
    dichos = [m.texto for m in entrada.historial if m.autor == "estudiante"] + [entrada.mensaje]
    for dicho in dichos:
        solo_la_respuesta = len(dicho.strip()) <= 12 and es_equivalente(dicho, esperada)
        if solo_la_respuesta or revela_solucion(dicho, esperada, enunciado):
            return False

    textos = [salida.texto] + [a.texto for a in salida.anotaciones if isinstance(a, AnotacionApunte)]
    return any(revela_solucion(texto, esperada, enunciado) for texto in textos)
