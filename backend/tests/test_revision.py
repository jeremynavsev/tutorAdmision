"""Pruebas de la revisión del banco con SymPy."""

import json

import pytest
from sympy import Rational

from app.config import RAIZ_BACKEND
from app.datos.revision import ComprobacionInvalida, _a_sympy, informe, main, revisar_ejercicio, valor_de_opcion
from app.esquemas import Ejercicio


def ejercicio(comprobacion: str | None, opciones: list[str], clave: str = "B", **extra) -> Ejercicio:
    datos = {
        "id": "x-01",
        "tema": "Prueba",
        "area": "Razonamiento matemático",
        "enunciado": "¿Cuánto da?",
        "opciones": opciones,
        "solucion": {"tipo": "opcion", "valor": clave},
        "pasos": ["Calcular."],
        "errores_comunes": [],
        "comprobacion": comprobacion,
    }
    return Ejercicio(**{**datos, **extra})


@pytest.mark.parametrize(
    ("opcion", "valor"),
    [
        ("50 gapes", 50),
        ("3 000", 3000),
        ("2,5", Rational(5, 2)),
        ("65 + 16²", 321),
        ("8000 − 24 × 250 − 8 × 125", 1000),
        ("Martes.", None),
        ("Entre 3 y 5 horas.", None),
    ],
)
def test_lee_el_valor_de_una_opcion(opcion, valor):
    assert valor_de_opcion(opcion) == valor


def test_las_incognitas_con_subindice_se_comparan_como_expresiones():
    assert valor_de_opcion("S₁₀ + 23") == _a_sympy("S10 + 11 + 12")


def test_verifica_una_clave_correcta():
    assert revisar_ejercicio(ejercicio("800/2^4", ["200", "50", "25"])).estado == "verificado"


def test_detecta_una_clave_mal_transcrita():
    resultado = revisar_ejercicio(ejercicio("800/2^4", ["200", "100", "50"], clave="A"))
    assert resultado.estado == "error" and "opción C" in resultado.detalle and "clave es A" in resultado.detalle


def test_detecta_dos_opciones_con_el_mismo_valor():
    resultado = revisar_ejercicio(ejercicio("2 + 2", ["3", "4", "2^2"]))
    assert resultado.estado == "error" and "varias opciones" in resultado.detalle


def test_detecta_una_comprobacion_que_no_da_ninguna_opcion():
    resultado = revisar_ejercicio(ejercicio("7", ["3", "4"]))
    assert resultado.estado == "error" and "ninguna opción" in resultado.detalle


def test_compara_con_la_solucion_cuando_no_es_de_opciones():
    bien = ejercicio("(20 - 5)/3", [], solucion={"tipo": "numero", "valor": "5"})
    mal = ejercicio("20/3", [], solucion={"tipo": "numero", "valor": "5"})
    assert revisar_ejercicio(bien).estado == "verificado"
    assert revisar_ejercicio(mal).estado == "error"


def test_sin_comprobacion_queda_para_revision_humana():
    assert revisar_ejercicio(ejercicio(None, ["a", "b"])).estado == "sin_comprobacion"


@pytest.mark.parametrize(
    "peligrosa",
    ["__import__('os')", "S10.func", "open('x')", "exec(1)", "x; y", "(1).__class__", "lambda: 1"],
)
def test_rechaza_codigo_en_la_comprobacion(peligrosa):
    with pytest.raises(ComprobacionInvalida):
        _a_sympy(peligrosa)
    assert revisar_ejercicio(ejercicio(peligrosa, ["1", "2"])).estado == "error"


def test_permite_las_funciones_de_la_lista():
    assert _a_sympy("6/igcd(26, 6)") == 3
    assert _a_sympy("Mod(302, 7)") == 1
    assert _a_sympy("binomial(5, 2)") == 10


def test_el_informe_cuenta_lo_pendiente():
    texto, bien = informe([ejercicio("1 + 1", ["1", "2"], revisado=True), ejercicio(None, ["a", "b"]).model_copy(update={"id": "x-02"})])
    assert bien
    assert "Verificados con SymPy: 1." in texto
    assert "Sin comprobación automática: 1. x-02" in texto
    assert "Pendientes de revisión humana: 1. x-02" in texto


def test_el_banco_de_ejemplo_pasa_la_revision(capsys):
    assert main([str(RAIZ_BACKEND / "ejercicios" / "banco.json")]) == 0
    assert "Verificados con SymPy: 2." in capsys.readouterr().out


def test_termina_con_error_si_algo_falla(tmp_path, capsys):
    malo = ejercicio("800/2^4", ["200", "100", "50"], clave="A").model_dump()
    ruta = tmp_path / "banco.json"
    ruta.write_text(json.dumps([malo], ensure_ascii=False), encoding="utf-8")
    assert main([str(ruta)]) == 1
    assert "✗ x-01" in capsys.readouterr().out
