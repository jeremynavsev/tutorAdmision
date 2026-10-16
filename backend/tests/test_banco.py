"""Pruebas del banco de ejercicios."""

import json
import subprocess

import pytest

from app.config import RAIZ_BACKEND
from app.datos.banco import BancoInvalido, leer_banco
from app.esquemas import Ejercicio

EJERCICIO = {
    "id": "paa-01",
    "tema": "Lógica",
    "area": "Razonamiento",
    "enunciado": "¿Cuál afirmación sucederá con certeza?",
    "opciones": ["uno", "dos", "tres", "cuatro"],
    "solucion": {"tipo": "opcion", "valor": "D"},
    "pasos": ["Revisar cada opción."],
    "errores_comunes": ["Elegir la A sin revisar todos los casos."],
}


def escribir(tmp_path, contenido) -> object:
    ruta = tmp_path / "banco.json"
    ruta.write_text(contenido if isinstance(contenido, str) else json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_el_banco_de_ejemplo_es_valido():
    banco = leer_banco(RAIZ_BACKEND / "ejercicios" / "banco.json")
    assert len(banco) == 2 and all(isinstance(e, Ejercicio) for e in banco)


def test_lee_un_banco_valido(tmp_path):
    assert leer_banco(escribir(tmp_path, [EJERCICIO]))[0].solucion.valor == "D"


@pytest.mark.parametrize("clave", ["E", "d", "42", ""])
def test_rechaza_una_clave_que_no_es_una_opcion(tmp_path, clave):
    malo = {**EJERCICIO, "solucion": {"tipo": "opcion", "valor": clave}}
    with pytest.raises(BancoInvalido, match="paa-01"):
        leer_banco(escribir(tmp_path, [malo]))


def test_rechaza_ids_repetidos(tmp_path):
    with pytest.raises(BancoInvalido, match="repetido"):
        leer_banco(escribir(tmp_path, [EJERCICIO, EJERCICIO]))


def test_dice_que_campo_falta(tmp_path):
    sin_pasos = {k: v for k, v in EJERCICIO.items() if k != "pasos"}
    with pytest.raises(BancoInvalido, match="paa-01.*pasos"):
        leer_banco(escribir(tmp_path, [sin_pasos]))


def test_avisa_si_el_json_esta_roto_o_no_existe(tmp_path):
    with pytest.raises(BancoInvalido, match="no es un JSON válido"):
        leer_banco(escribir(tmp_path, "[{"))
    with pytest.raises(BancoInvalido, match="No existe"):
        leer_banco(tmp_path / "no-existe.json")


def test_la_carpeta_del_banco_privado_no_se_sube_a_git():
    privado = RAIZ_BACKEND / "ejercicios" / "privado" / "banco.json"
    resultado = subprocess.run(["git", "check-ignore", "-q", str(privado)], cwd=RAIZ_BACKEND, check=False)
    assert resultado.returncode == 0, "backend/ejercicios/privado/ tiene que estar en el .gitignore"


def test_no_hay_ruta_publica_que_liste_los_ejercicios():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/ejercicios").status_code == 404
