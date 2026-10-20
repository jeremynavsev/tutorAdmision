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


# Sin respaldos de Gemini, para que estas pruebas hablen solo del orden entre proveedores.
TODAS = dict(gemini_api_key="g", groq_api_key="q", gemini_modelos_respaldo=())


def nombres(config: Configuracion) -> list[str]:
    return [p.nombre for p in proveedores_disponibles(config)]


def test_por_defecto_groq_va_primero():
    assert nombres(Configuracion(**TODAS)) == ["groq", "gemini"]


def test_solo_entran_los_proveedores_con_llave():
    config = Configuracion(gemini_api_key="g", groq_api_key="", gemini_modelos_respaldo=())
    assert nombres(config) == ["gemini"]


def test_el_orden_se_puede_cambiar():
    config = Configuracion(**TODAS, orden_proveedores=("gemini", "groq"))
    assert nombres(config) == ["gemini", "groq"]


def test_los_que_no_se_nombran_van_al_final_y_los_desconocidos_se_ignoran():
    # Un nombre que no existe (por ejemplo, de un .env viejo) se ignora sin romper nada.
    config = Configuracion(**TODAS, orden_proveedores=("gemini", "deepseek"))
    assert nombres(config) == ["gemini", "groq"]


def test_con_foto_la_cadena_por_defecto_llega_a_gemini():
    con_foto = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]}]
    llamadas: dict = {}
    r = completar(
        con_foto,
        proveedores=proveedores_disponibles(Configuracion(**TODAS)),
        crear_cliente=fabrica({"groq": "{}", "gemini": '{"ok": 1}'}, llamadas),
    )
    assert r.proveedor == "gemini" and "groq" not in llamadas


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
        proveedores=[proveedor("groq", acepta_imagenes=False), proveedor("gemini")],
        crear_cliente=fabrica({"groq": '{"ok": 1}', "gemini": '{"ok": 2}'}, llamadas),
    )
    assert r.proveedor == "gemini"
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
    config = Configuracion(gemini_api_key="g", groq_api_key="q", gemini_modelos_respaldo=("otro-gemini",))
    extras = [(p.etiqueta, p.extras) for p in proveedores_disponibles(config)]
    assert extras == [("groq", {}), ("gemini", {"reasoning_effort": "low"}), ("gemini/otro-gemini", {"reasoning_effort": "low"})]


def test_el_razonamiento_se_puede_dejar_normal():
    config = Configuracion(gemini_api_key="g", gemini_razonamiento="normal")
    assert all(p.extras == {} for p in proveedores_disponibles(config))


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
        proveedores=[proveedor("groq"), proveedor("gemini")],
        crear_cliente=fabrica({"groq": error, "gemini": '{"ok": 1}'}, {}),
    )
    assert r.proveedor == "gemini"


# ---------- Modelos de respaldo de Gemini ----------


def etiquetas(config: Configuracion) -> list[str]:
    return [p.etiqueta for p in proveedores_disponibles(config)]


def test_los_respaldos_de_gemini_van_justo_despues_del_principal():
    config = Configuracion(gemini_api_key="g", groq_api_key="q")
    assert etiquetas(config) == ["groq", "gemini", "gemini/gemini-3.5-flash", "gemini/gemini-3.1-flash-lite"]


def test_los_respaldos_usan_la_misma_llave_y_leen_fotos():
    respaldos = [p for p in proveedores_disponibles(Configuracion(gemini_api_key="la-llave")) if p.es_respaldo]
    assert len(respaldos) == 2
    assert all(p.llave == "la-llave" and p.acepta_imagenes and p.nombre == "gemini" for p in respaldos)


def test_sin_llave_de_gemini_no_hay_respaldos():
    assert etiquetas(Configuracion(groq_api_key="q")) == ["groq"]


def test_no_se_repite_el_modelo_principal_como_respaldo():
    config = Configuracion(gemini_api_key="g", gemini_modelo="a", gemini_modelos_respaldo=("a", "b"))
    assert etiquetas(config) == ["gemini", "gemini/b"]


def test_si_el_principal_agota_su_cuota_una_foto_la_atiende_el_respaldo():
    con_foto = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]}]
    config = Configuracion(gemini_api_key="g", groq_api_key="q", gemini_modelo="principal", gemini_modelos_respaldo=("respaldo",))
    modelos_usados = []

    def crear(p: Proveedor, tiempo_maximo: float):
        modelos_usados.append(p.modelo)
        return ClienteFalso(falla_http(429) if p.modelo == "principal" else '{"ok": 1}', [])

    r = completar(con_foto, proveedores=proveedores_disponibles(config), crear_cliente=crear)
    assert (r.proveedor, r.modelo) == ("gemini", "respaldo")
    assert modelos_usados == ["principal", "respaldo"]


def test_los_fallos_dicen_que_modelo_de_respaldo_fallo():
    config = Configuracion(gemini_api_key="g", gemini_modelo="principal", gemini_modelos_respaldo=("respaldo",))
    with pytest.raises(SinProveedores) as error:
        completar(MENSAJES, proveedores=proveedores_disponibles(config), crear_cliente=lambda p, t: ClienteFalso(falla_http(429), []))
    assert error.value.fallos == ["gemini: HTTP 429", "gemini/respaldo: HTTP 429"]
