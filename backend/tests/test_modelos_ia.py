"""Pruebas de la cadena de proveedores, con clientes falsos (no gastan cuota)."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from app.config import Configuracion
from app.servicios.modelos_ia import Proveedor, SinProveedores, completar, proveedores_disponibles

PETICION = httpx.Request("POST", "https://proveedor.falso/v1/chat/completions")


def proveedor(nombre: str, acepta_imagenes: bool = True) -> Proveedor:
    return Proveedor(nombre=nombre, url_base="https://falso", modelo=f"{nombre}-modelo", llave="llave", acepta_imagenes=acepta_imagenes)


def falla_http(codigo: int) -> Exception:
    return openai.APIStatusError("falló", response=httpx.Response(codigo, request=PETICION), body=None)


class ClienteFalso:
    """Imita al cliente de OpenAI: responde un texto o lanza un error, y anota las llamadas."""

    def __init__(self, resultado, llamadas: list):
        self._resultado = resultado
        self._llamadas = llamadas
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **argumentos):
        self._llamadas.append(argumentos)
        if isinstance(self._resultado, Exception):
            raise self._resultado
        mensaje = SimpleNamespace(content=self._resultado)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


def fabrica(resultados: dict, llamadas: dict):
    """Crea clientes falsos según el nombre del proveedor."""

    def crear(p: Proveedor, tiempo_maximo: float):
        llamadas.setdefault(p.nombre, [])
        return ClienteFalso(resultados[p.nombre], llamadas[p.nombre])

    return crear


MENSAJES = [{"role": "user", "content": "hola"}]


def test_solo_entran_los_proveedores_con_llave_y_en_orden():
    config = Configuracion(gemini_api_key="g", groq_api_key="", mistral_api_key="m")
    assert [p.nombre for p in proveedores_disponibles(config)] == ["gemini", "mistral"]


def test_usa_el_modelo_configurado():
    config = Configuracion(groq_api_key="x", groq_modelo="otro-modelo")
    assert proveedores_disponibles(config)[0].modelo == "otro-modelo"


def test_responde_el_primero_si_funciona():
    llamadas: dict = {}
    r = completar(
        MENSAJES,
        proveedores=[proveedor("gemini"), proveedor("groq")],
        crear_cliente=fabrica({"gemini": '{"ok": 1}', "groq": "no debería usarse"}, llamadas),
    )
    assert (r.proveedor, r.texto) == ("gemini", '{"ok": 1}')
    assert "groq" not in llamadas


@pytest.mark.parametrize(
    "error",
    [
        falla_http(503),
        falla_http(429),
        falla_http(403),
        openai.APITimeoutError(request=PETICION),
        openai.APIConnectionError(request=PETICION),
    ],
)
def test_si_el_primero_falla_pasa_al_siguiente(error):
    r = completar(
        MENSAJES,
        proveedores=[proveedor("gemini"), proveedor("groq")],
        crear_cliente=fabrica({"gemini": error, "groq": '{"ok": 1}'}, {}),
    )
    assert r.proveedor == "groq"


def test_una_respuesta_vacia_cuenta_como_fallo():
    r = completar(
        MENSAJES,
        proveedores=[proveedor("gemini"), proveedor("groq")],
        crear_cliente=fabrica({"gemini": "   ", "groq": '{"ok": 1}'}, {}),
    )
    assert r.proveedor == "groq"


def test_si_todos_fallan_dice_que_le_paso_a_cada_uno():
    with pytest.raises(SinProveedores) as error:
        completar(
            MENSAJES,
            proveedores=[proveedor("gemini"), proveedor("groq")],
            crear_cliente=fabrica({"gemini": falla_http(503), "groq": openai.APITimeoutError(request=PETICION)}, {}),
        )
    assert error.value.fallos == ["gemini: HTTP 503", "groq: tiempo agotado"]


def test_sin_llaves_avisa():
    with pytest.raises(SinProveedores, match="no hay ninguna llave"):
        completar(MENSAJES, proveedores=[])


def test_con_foto_se_salta_al_que_no_lee_imagenes():
    llamadas: dict = {}
    con_foto = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Este es mi ejercicio"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}},
            ],
        }
    ]
    r = completar(
        con_foto,
        proveedores=[proveedor("groq", acepta_imagenes=False), proveedor("mistral")],
        crear_cliente=fabrica({"groq": '{"ok": 1}', "mistral": '{"ok": 2}'}, llamadas),
    )
    assert r.proveedor == "mistral"
    assert "groq" not in llamadas


def test_pide_json_solo_cuando_se_le_indica():
    llamadas: dict = {}
    crear = fabrica({"gemini": "{}"}, llamadas)
    completar(MENSAJES, proveedores=[proveedor("gemini")], crear_cliente=crear)
    completar(MENSAJES, json=False, proveedores=[proveedor("gemini")], crear_cliente=crear)
    assert llamadas["gemini"][0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in llamadas["gemini"][1]


# ---------- Parámetros propios del proveedor (razonamiento de Gemini) ----------


def test_gemini_pide_poco_razonamiento_por_defecto():
    gemini = proveedores_disponibles(Configuracion(gemini_api_key="g", groq_api_key="q"))
    assert gemini[0].extras == {"reasoning_effort": "low"}
    assert gemini[1].extras == {}


def test_el_razonamiento_se_puede_dejar_normal():
    config = Configuracion(gemini_api_key="g", gemini_razonamiento="normal")
    assert proveedores_disponibles(config)[0].extras == {}


def test_los_extras_viajan_en_la_consulta():
    llamadas: dict = {}
    con_extras = Proveedor("gemini", "https://falso", "m", "llave", True, extras={"reasoning_effort": "low"})
    completar(MENSAJES, proveedores=[con_extras], crear_cliente=fabrica({"gemini": "{}"}, llamadas))
    assert llamadas["gemini"][0]["reasoning_effort"] == "low"
    assert llamadas["gemini"][0]["response_format"] == {"type": "json_object"}


def test_si_el_proveedor_rechaza_los_extras_reintenta_sin_ellos():
    llamadas: list = []

    class RechazaExtras:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.crear))

        def crear(self, **argumentos):
            llamadas.append(argumentos)
            if "reasoning_effort" in argumentos:
                raise openai.BadRequestError("no", response=httpx.Response(400, request=PETICION), body=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": 1}'))])

    con_extras = Proveedor("gemini", "https://falso", "m", "llave", True, extras={"reasoning_effort": "low"})
    r = completar(MENSAJES, proveedores=[con_extras], crear_cliente=lambda p, t: RechazaExtras())
    assert r.texto == '{"ok": 1}'
    assert len(llamadas) == 2 and "reasoning_effort" not in llamadas[1]


def test_un_400_sin_extras_si_cuenta_como_fallo():
    error = openai.BadRequestError("no", response=httpx.Response(400, request=PETICION), body=None)
    r = completar(
        MENSAJES,
        proveedores=[proveedor("groq"), proveedor("mistral")],
        crear_cliente=fabrica({"groq": error, "mistral": '{"ok": 1}'}, {}),
    )
    assert r.proveedor == "mistral"
