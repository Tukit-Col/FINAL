"""Fase 5 de QA: el asistente NL2C ante un modelo que obedece al atacante (ADV-12...18).

Cada caso lee su fixture de `ensayos/adversariales/fixtures/nl2c/`: el texto hostil del
acudiente (datos ficticios), la respuesta del modelo y la condicion de exito, escrita antes
de correr. La respuesta es el peor caso: un doble en `nl2c._LLAMAR` devuelve lo que el
atacante pidio (pagar, borrar, ver otro kit, herramientas fuera de la lista, marcado, una
avalancha de propuestas). Nada llama a Gemini; lo que se prueba es lo que el SERVIDOR hace con
eso, por las rutas reales (`/v1/nl2c/interpretar` y `/v1/kits/{id}/asistente/proponer`).

`test_nl2c.py`, `test_nl2c_lote.py` y `ensayos/nl2c/` (del equipo) ya prueban la lista blanca,
los codigos del validador, los topes, el 404 del kit ajeno y la marca del texto; no se repiten.
Aqui se suma lo que no cubren:

- **Las llamadas al modelo por peticion.** El doble las cuenta: 1 por pedido, 0 en lo que se
  resuelve sin el (ayuda, entrada invalida, sin sesion, kit ajeno o no publicado) y 1 sin
  reintento cuando el modelo no contesta a tiempo.
- **Nada se escribe.** La tabla de trabajos queda igual y `trabajos.ver` es lo unico que se
  pide; las propuestas llegan con `aplicable` y las aplica el padre por su ruta.
- **Lo que ve el padre pasa la web.** La spec se valida con las reglas de `validarEspec`
  (`apps/web/src/components/asistente/espec.ts`), reimplementadas aqui: 8 tipos, 13
  componentes, textos de 1 a 160 caracteres.
- **Ni la tarjeta ni lo ajeno salen.** Ni al modelo, ni a la respuesta, ni a la bitacora.

Lo que se espera rojo va sin `xfail`: es candidato a hallazgo hasta la corrida. La corrida
oe5 abrio H-A-65 (ADV-15, el motivo de `sin_accion` crudo en la bitacora).
"""

from __future__ import annotations

import io
import json
import re
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

# Reutiliza el montaje de rutas de test_nl2c (identidad falsa, trabajo sembrado, kit de tres renglones).
from _ayudas_nl2c import H, OTRO, PADRE, sembrar
from _ayudas_nl2c import kit_de_tres as _kit
from test_nl2c_rutas import cliente  # noqa: F401  (cliente es una fixture)
from tukit_inteligencia import (  # noqa: F401  (api antes que routers)
    api,
    gemini,
    nl2c,
    nl2c_flujo,
    nl2c_kit,
    trabajos,
)
from tukit_inteligencia.modelos import Base, EstadoTrabajo

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = RAIZ / "ensayos" / "adversariales" / "fixtures" / "nl2c"
CASOS_NL2C = sorted(ruta.stem for ruta in FIXTURES.glob("ADV-*.json"))
OWASP_DEL_ASISTENTE = {"LLM01", "LLM02", "LLM05", "LLM06", "LLM10"}

# Las reglas de `validarEspec` (espec.ts): lo que la web pinta o descarta entero.
TIPOS_WEB = {
    "TarjetaPersonaje",
    "SelectorPresupuesto",
    "Prioridades",
    "ResumenRestricciones",
    "PropuestaCambio",
    "PropuestaDescarte",
    "ExplicacionKit",
    "ResumenLote",
}
MAX_COMPONENTES_WEB = 13
MAX_TEXTO_WEB = 160


def _fixture(prefijo: str) -> dict[str, Any]:
    (ruta,) = FIXTURES.glob(f"{prefijo}-*.json")
    return json.loads(ruta.read_text())


def _intento(caso: dict[str, Any], intento_id: str) -> dict[str, Any]:
    return next(i for i in caso["intentos"] if i["id"] == intento_id)


def _texto(intento: dict[str, Any]) -> str:
    if "texto_repetido" in intento:
        frase, largo = intento["texto_repetido"]["frase"], intento["texto_repetido"]["largo"]
        return (frase * (largo // len(frase) + 1))[:largo]
    return intento["texto"]


class ModeloQueObedece:
    """El `_LLAMAR` del asistente: cuenta cada llamada y devuelve la respuesta del fixture."""

    def __init__(self, respuesta: dict[str, Any] | None, *, demora: float = 0.0) -> None:
        self.respuesta = respuesta or {"llamadas": [], "tokens_entrada": 0, "tokens_salida": 0}
        self.demora = demora
        self.vistos: list[dict[str, Any]] = []

    @property
    def llamadas(self) -> int:
        return len(self.vistos)

    def __call__(self, sistema, usuario, _declaraciones, permitidas) -> nl2c.RespuestaModelo:  # noqa: ANN001
        self.vistos.append({"sistema": sistema, "usuario": usuario, "permitidas": permitidas})
        if self.demora:
            time.sleep(self.demora)
        # Copia: el servidor filtra la lista y no debe tocar la del fixture.
        llamadas = json.loads(json.dumps(self.respuesta["llamadas"]))
        return nl2c.RespuestaModelo(
            llamadas, self.respuesta["tokens_entrada"], self.respuesta["tokens_salida"]
        )


def _modelo(monkeypatch: pytest.MonkeyPatch, intento: dict[str, Any], **kw: Any) -> ModeloQueObedece:
    doble = ModeloQueObedece(intento.get("respuesta_modelo"), **kw)
    monkeypatch.setattr(nl2c, "_LLAMAR", doble)
    return doble


def _cadenas(valor: Any) -> list[str]:
    """Todas las cadenas de una respuesta, claves incluidas."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [c for k, v in valor.items() for c in (*_cadenas(k), *_cadenas(v))]
    if isinstance(valor, list):
        return [c for v in valor for c in _cadenas(v)]
    return []


def _textos_de_la_web(componente: dict[str, Any]) -> list[str]:
    """Los campos que la web exige con `texto()` (1 a 160 caracteres), segun el tipo."""
    p = componente["props"]
    tarjetas = [p[k] for k in ("antes", "despues", "producto") if isinstance(p.get(k), dict)]
    campos = {
        "TarjetaPersonaje": [p.get("nombre")],
        "PropuestaCambio": [p.get(k) for k in ("trabajo_id", "perfil", "item_id", "descripcion")],
        "PropuestaDescarte": [
            p.get(k) for k in ("trabajo_id", "perfil", "item_id", "descripcion", "motivo_texto")
        ],
        "ResumenLote": [p.get("categoria"), p.get("texto")],
        "ExplicacionKit": [p.get("perfil")],
    }.get(componente["tipo"], [])
    return campos + [t.get(k) for t in tarjetas for k in ("sku", "nombre")]


def _la_web_la_pinta(ui: dict[str, Any]) -> list[str]:
    """Lo que haria fallar `validarEspec`; vacia si la web la acepta."""
    fallas: list[str] = []
    if ui.get("version") != 1 or not isinstance(ui.get("componentes"), list):
        return ["spec sin version 1 o sin componentes"]
    if len(ui["componentes"]) > MAX_COMPONENTES_WEB:
        fallas.append(f"{len(ui['componentes'])} componentes")
    for c in ui["componentes"]:
        if c.get("tipo") not in TIPOS_WEB:
            fallas.append(f"tipo {c.get('tipo')!r}")
            continue
        for t in _textos_de_la_web(c):
            if not (isinstance(t, str) and 0 < len(t) <= MAX_TEXTO_WEB):
                fallas.append(f"{c['tipo']}: texto de {len(t) if isinstance(t, str) else t!r}")
        propuesta = c["tipo"] in ("PropuestaCambio", "PropuestaDescarte")
        if propuesta and not isinstance(c["props"].get("aplicable"), bool):
            fallas.append(f"{c['tipo']}: aplicable no es booleano")
        if c["tipo"] == "ExplicacionKit" and any(len(k) > 30 for k in c["props"].get("por_nivel", {})):
            fallas.append("ExplicacionKit: nivel de mas de 30")
    return fallas


async def _filas(motor) -> dict[str, list[tuple]]:  # noqa: ANN001
    """Todas las filas de todas las tablas de inteligencia: lo que el asistente no debe cambiar."""
    async with motor.sesion() as db:
        return {
            tabla.name: sorted(map(tuple, (await db.execute(select(tabla))).all()), key=repr)
            for tabla in Base.metadata.sorted_tables
        }


@pytest.fixture()
def lecturas(cliente, monkeypatch: pytest.MonkeyPatch) -> list[str]:  # noqa: F811
    """`trabajos.ver` es lo unico de trabajos que el asistente puede pedir: se anota cada pedido."""
    pedidos: list[str] = []

    async def ver_falso(_motor, trabajo_id, **_kw):  # noqa: ANN001
        pedidos.append(str(trabajo_id))
        return {"kits": [_kit()]}

    monkeypatch.setattr(trabajos, "ver", ver_falso)
    return pedidos


@pytest.fixture(autouse=True)
def _caso(request: pytest.FixtureRequest, record_property) -> None:
    """El caso del catalogo adversarial sale del nombre de la clase (`TestADV12...` -> ADV-12)."""
    marca = re.match(r"TestADV(\d\d)", request.node.cls.__name__ if request.node.cls else "")
    if marca:
        record_property("caso_adv", f"ADV-{marca.group(1)}")


class TestLosFixturesDelNl2cSonCoherentes:
    @pytest.mark.parametrize("nombre", CASOS_NL2C)
    def test_cada_fixture_trae_su_riesgo_y_su_condicion_de_exito(self, nombre):
        caso = json.loads((FIXTURES / f"{nombre}.json").read_text())
        assert nombre.startswith(caso["fixture_id"] + "-") and caso["caso"] == caso["fixture_id"]
        assert caso["origen"] == "sintetico"
        assert caso["owasp"] and set(caso["owasp"]) <= OWASP_DEL_ASISTENTE
        assert caso["ensayo_ids"] and all(e.startswith("NFR-") for e in caso["ensayo_ids"])
        assert caso["condicion_exito"].strip()
        ids = [i["id"] for i in caso["intentos"]]
        assert ids and len(ids) == len(set(ids))
        assert all(i["condicion_exito"] for i in caso["intentos"])

    def test_estan_los_ocho_casos_y_los_cuatro_riesgos_del_bloque(self):
        assert [n[:6] for n in CASOS_NL2C] == [f"ADV-{n}" for n in range(12, 20)]
        riesgos = {r for n in CASOS_NL2C for r in json.loads((FIXTURES / f"{n}.json").read_text())["owasp"]}
        assert {"LLM01", "LLM05", "LLM06", "LLM10"} <= riesgos


async def _pedir(
    cliente,  # noqa: ANN001, F811
    intento: dict[str, Any],
    trabajo_id: uuid.UUID | None = None,
    *,
    ruta: str | None = None,
    headers: dict[str, str] | None = H,
):
    """El intento por su ruta real: `interpretar` sin kit o `proponer` sobre el trabajo sembrado."""
    cuerpo = {"texto": _texto(intento)}
    if (ruta or intento["ruta"]) == "interpretar":
        return await cliente.post("/v1/nl2c/interpretar", json=cuerpo, headers=headers)
    return await cliente.post(
        f"/v1/kits/{trabajo_id}/asistente/proponer", json={**cuerpo, "perfil": "Ahorrador"}, headers=headers
    )


def _exigir(intento: dict[str, Any], r, doble: ModeloQueObedece) -> dict[str, Any]:  # noqa: ANN001
    """La parte de la condicion de exito que vale para cualquier caso; devuelve el cuerpo."""
    esperado = intento["condicion_exito"]
    cuerpo = r.json()
    assert r.status_code == esperado["http"], cuerpo
    assert doble.llamadas == esperado["llamadas_al_modelo"]
    if "estado" in esperado:
        assert cuerpo["estado"] == esperado["estado"], cuerpo
    if "error" in esperado:
        assert cuerpo["error"] == esperado["error"]
    if "mensaje" in esperado:
        assert cuerpo["mensaje"] == esperado["mensaje"]
    visible = json.dumps(cuerpo, ensure_ascii=False)
    for prohibido in esperado.get("prohibido", []):
        assert prohibido not in visible, f"{prohibido!r} llego al padre"
    for prohibido in esperado.get("prohibido_en_prompt", []):
        assert all(prohibido not in v["usuario"] for v in doble.vistos), f"{prohibido!r} llego al modelo"
    if "tipos" in esperado:
        assert [c["tipo"] for c in cuerpo["ui"]["componentes"]] == esperado["tipos"]
    if esperado.get("valida_en_la_web"):
        assert _la_web_la_pinta(cuerpo["ui"]) == []
    if esperado.get("sin_marcado"):
        assert not [t for t in _cadenas(cuerpo.get("ui")) if "<" in t or ">" in t]
    return cuerpo


def _bitacora() -> str:
    return json.dumps(nl2c.BITACORA, ensure_ascii=False, default=str)


def _rechazadas() -> list[str]:
    (registro,) = [e for e in nl2c.BITACORA if e["evento"] == "proponer_propuesta"]
    return list(registro["rechazadas"])


@pytest.mark.nfr("NFR-SEG-06")
class TestADV12PagarElKit:
    """LLM01 y LLM06: el texto pide pagar con tarjeta y confirmar, y el modelo obedece."""

    async def test_en_el_kit_solo_queda_una_propuesta_que_el_padre_tiene_que_aceptar(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        lecturas,
        record_property,
    ):
        intento = _intento(_fixture("ADV-12"), "kit")
        tid = await sembrar(motor)
        antes = await _filas(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        (propuesta,) = cuerpo["ui"]["componentes"]
        assert propuesta["props"]["aplicable"] is True
        assert propuesta["props"]["trabajo_id"] == str(tid)
        assert _rechazadas() == intento["condicion_exito"]["rechazadas"]
        # El segundo filtro de `consultar_modelo` ya quito pagar_orden y confirmar_compra.
        assert doble.vistos[0]["permitidas"] == nl2c.HERRAMIENTAS_KIT
        # La tarjeta entera: "4111" suelto podria salir en una huella hexadecimal.
        assert not [t for t in ("4111 1111 1111 1111", "4111111111111111", "pagar") if t in _bitacora()]
        assert await _filas(motor) == antes
        assert lecturas == [str(tid)]

    async def test_al_empezar_la_tarjeta_no_sale_y_el_pago_no_cambia_las_preferencias(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        intento = _intento(_fixture("ADV-12"), "empezar")
        antes = await _filas(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert cuerpo["r"]["preferencias_PRM"]["personajes"] == ["Bluey"]
        assert set(cuerpo["preferencias"]) <= {
            "pesos",
            "disposicion_sobreprecio",
            "prioridad",
            "presupuesto_por_hijo",
            "marcas_excluidas",
            "solo_disponibles",
            "personaje_por_hijo",
        }
        assert doble.vistos[0]["permitidas"] == nl2c.HERRAMIENTAS_INTERPRETAR
        assert not [t for t in ("4111 1111 1111 1111", "4111111111111111") if t in _bitacora()]
        assert await _filas(motor) == antes


@pytest.mark.nfr("NFR-SEG-06")
class TestADV13BorrarLaCuenta:
    """LLM01 y LLM06: el texto pide borrar la cuenta y el kit; el modelo inventa herramientas."""

    async def test_los_descartes_quedan_propuestos_y_nada_se_borra(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        lecturas,
        record_property,
    ):
        intento = _intento(_fixture("ADV-13"), "kit")
        tid = await sembrar(motor)
        antes = await _filas(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        propuestas = cuerpo["ui"]["componentes"]
        assert len(propuestas) <= intento["condicion_exito"]["max_propuestas"]
        assert all(p["props"]["aplicable"] is True for p in propuestas)
        assert {p["props"]["item_id"] for p in propuestas} == {ln["item_id"] for ln in _kit()["lineas"]}
        assert _rechazadas() == intento["condicion_exito"]["rechazadas"]
        assert await _filas(motor) == antes
        assert lecturas == [str(tid)]

    @pytest.mark.parametrize("intento_id", ["solo_inventadas", "empezar"])
    async def test_si_todo_esta_fuera_de_la_lista_el_padre_ve_el_mensaje_fijo(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        intento_id,
        record_property,
    ):
        intento = _intento(_fixture("ADV-13"), intento_id)
        tid = await sembrar(motor)
        antes = await _filas(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert "ui" not in cuerpo and "propuesta_id" not in cuerpo
        assert "suprimir" not in _bitacora()
        assert await _filas(motor) == antes


@pytest.mark.nfr("NFR-SEG-06")
class TestADV14DatosDeOtroAcudiente:
    """LLM01, LLM02 y LLM06: el texto pide el kit y el correo de otra familia."""

    async def test_lo_que_ve_el_padre_sale_solo_de_su_kit(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        lecturas,
        record_property,
    ):
        caso = _fixture("ADV-14")
        intento = _intento(caso, "kit")
        tid = await sembrar(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        (propuesta,) = cuerpo["ui"]["componentes"]
        assert propuesta["props"]["trabajo_id"] == str(tid)
        assert propuesta["props"]["item_id"] == _kit()["lineas"][1]["item_id"]
        assert _rechazadas() == intento["condicion_exito"]["rechazadas"]
        for ajeno in intento["condicion_exito"]["prohibido"]:
            assert ajeno not in _bitacora()
        assert lecturas == [str(tid)]

    async def test_el_kit_de_otro_da_el_mismo_404_sin_llamar_al_modelo_ni_leer_el_kit(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        lecturas,
        record_property,
    ):
        intento = _intento(_fixture("ADV-14"), "kit_ajeno")
        ajeno = await sembrar(motor, usuario=OTRO)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, ajeno), doble)
        inexistente = (await _pedir(cliente, intento, uuid.uuid4())).json()

        record_property("llamadas_al_modelo", doble.llamadas)
        assert cuerpo == inexistente
        assert lecturas == []
        assert [e["evento"] for e in nl2c.BITACORA] == ["proponer_denegado", "proponer_denegado"]
        # La bitacora lleva la huella del portador, no su id.
        assert str(PADRE) not in _bitacora() and str(OTRO) not in _bitacora()


@pytest.mark.nfr("NFR-SEG-06")
class TestADV15HerramientasFueraDeLista:
    """LLM05 y LLM06: el modelo intenta escribir o usar herramientas que su ruta no tiene."""

    async def test_lo_que_no_es_de_la_lista_se_descarta_y_el_precio_sale_del_kit(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        lecturas,
        record_property,
    ):
        intento = _intento(_fixture("ADV-15"), "kit_escribir")
        esperado = intento["condicion_exito"]
        tid = await sembrar(motor)
        antes = await _filas(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        (propuesta,) = cuerpo["ui"]["componentes"]
        props = propuesta["props"]
        assert props["delta_cop"] == esperado["delta_cop"]
        assert props["despues"]["precio_unitario"] == esperado["precio_despues"]
        assert props["trabajo_id"] == str(tid) and props["item_id"] == _kit()["lineas"][0]["item_id"]
        # El modelo mando `aplicable: false`; la tarjeta la arma el servidor.
        assert props["aplicable"] is True
        assert doble.vistos[0]["permitidas"] == nl2c.HERRAMIENTAS_KIT
        assert _rechazadas() == esperado["rechazadas"]
        assert await _filas(motor) == antes
        assert lecturas == [str(tid)]

    # H-A-65: sale XPASS(strict) sobre la limpieza (el motivo ya llega a la bitacora como un codigo) y se
    # quita el xfail.
    async def test_al_empezar_el_motivo_de_sin_accion_llega_a_la_bitacora_como_un_codigo(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        intento = _intento(_fixture("ADV-15"), "empezar_motivo_libre")
        doble = _modelo(monkeypatch, intento)

        _exigir(intento, await _pedir(cliente, intento), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        (registro,) = [e for e in nl2c.BITACORA if e["evento"] == "interpretar_sin_accion"]
        # La ruta del kit ya lo acota a la lista (`validar_llamadas_kit`); aqui se exige lo mismo.
        assert registro["motivo"] in intento["condicion_exito"]["motivo_en_bitacora"]
        assert "<script" not in _bitacora()


def _textos_del_modelo(cuerpo: dict[str, Any]) -> list[str]:
    """Los textos de la pantalla que no son dato del catalogo (sku, marca, nivel e imagen si lo son)."""
    salida: list[str] = []
    for c in cuerpo["ui"]["componentes"]:
        props = {k: v for k, v in c["props"].items() if k not in ("antes", "despues", "producto")}
        salida += _cadenas(props)
        for k in ("antes", "despues", "producto"):
            if isinstance(c["props"].get(k), dict):
                salida += _cadenas(c["props"][k].get("nombre"))
    return salida + _cadenas({k: cuerpo.get(k) for k in ("mensaje", "resumen", "ajustes", "contexto")})


@pytest.mark.nfr("NFR-SEG-06")
class TestADV16ComponentesFueraDeLista:
    """LLM05: el modelo intenta meter estructura, marcado o un componente de mas en la pantalla."""

    @pytest.mark.parametrize("intento_id", ["kit_estructura", "kit_explicacion_y_lote"])
    async def test_en_el_kit_la_pantalla_solo_trae_componentes_de_la_lista_y_textos_del_servidor(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        intento_id,
        record_property,
    ):
        intento = _intento(_fixture("ADV-16"), intento_id)
        tid = await sembrar(motor)
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento, tid), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert {c["tipo"] for c in cuerpo["ui"]["componentes"]} <= nl2c.COMPONENTES_UI == TIPOS_WEB
        assert not [t for t in _textos_del_modelo(cuerpo) if "<" in t or ">" in t]
        assert _rechazadas() == intento["condicion_exito"]["rechazadas"]

    async def test_al_empezar_solo_salen_personajes_del_catalogo(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        intento = _intento(_fixture("ADV-16"), "empezar_personaje_con_marcado")
        doble = _modelo(monkeypatch, intento)

        cuerpo = _exigir(intento, await _pedir(cliente, intento), doble)

        record_property("llamadas_al_modelo", doble.llamadas)
        componentes = cuerpo["ui"]["componentes"]
        nombres = [c["props"]["nombre"] for c in componentes if c["tipo"] == "TarjetaPersonaje"]
        assert nombres == ["Bluey"]
        assert cuerpo["r"]["preferencias_PRM"]["personajes"] == ["Bluey"]
        assert not [t for t in _textos_del_modelo(cuerpo) if "<" in t or ">" in t]
        assert not [t for t in _cadenas(cuerpo["r"]) if "<" in t]


def _kit_de_cuadernos(renglones: int) -> dict[str, Any]:
    """Un kit sintetico de cuadernos, cada uno con dos alternativas mas baratas."""

    def linea(n: int) -> dict[str, Any]:
        return {
            "item_id": f"00000000-0000-4000-8000-{n:012d}",
            "descripcion": f"Cuaderno cuadriculado {n}",
            "informativa": False,
            "unidades_a_comprar": 1,
            "subtotal_linea": 9000,
            "producto_elegido": {
                "sku": f"CU-{n}",
                "nombre": f"Cuaderno cuadriculado CU-{n}",
                "marca": "Norma",
                "nivel": "premium",
                "precio": 9000,
                "imagen_url": None,
            },
            "alternativas": [
                {"sku": f"CU-{n}-{x}", "nombre": f"Cuaderno CU-{n}-{x}", "nivel": nivel, "precio_cop": precio}
                for x, nivel, precio in (("B", "economico", 5000), ("C", "confiable", 7000))
            ],
        }

    return {
        "perfil": "Ahorrador",
        "total": {"monto": 9000 * renglones},
        "consolidaciones": [],
        "lineas": [linea(n) for n in range(1, renglones + 1)],
    }


@pytest.mark.nfr("NFR-SEG-06")
class TestADV17LotesDemasiadoGrandes:
    """LLM10 y LLM06: el modelo devuelve una avalancha de propuestas sobre un kit de 90 renglones."""

    async def test_la_avalancha_queda_en_5_sueltas_y_12_propuestas_con_el_aviso_del_tope(
        self, monkeypatch, record_property
    ):
        caso = _fixture("ADV-17")
        intento = _intento(caso, "kit_avalancha")
        esperado = intento["condicion_exito"]
        doble = _modelo(monkeypatch, intento)
        kit = _kit_de_cuadernos(caso["kit"]["renglones"])

        cuerpo, res = await nl2c_flujo.proponer_en_kit(_texto(intento), kit, PADRE, "t-adv17")

        record_property("llamadas_al_modelo", doble.llamadas)
        componentes = cuerpo["ui"]["componentes"]
        assert cuerpo["estado"] == esperado["estado"] and doble.llamadas == esperado["llamadas_al_modelo"]
        assert res.sueltas <= esperado["max_sueltas"]
        assert len(res.propuestas) <= esperado["max_propuestas"]
        assert len(componentes) <= esperado["max_componentes"]
        assert componentes[0]["tipo"] == "ResumenLote"
        assert esperado["aviso_tope"] in componentes[0]["props"]["texto"]
        assert res.lote["fuera_por_tope"] > 0
        for codigo, minimo in esperado["rechazadas_cuenta"].items():
            assert res.rechazadas.count(codigo) >= minimo, (codigo, res.rechazadas)
        assert _la_web_la_pinta(cuerpo["ui"]) == []
        # Ningun renglon se propone dos veces, ni entre las sueltas y el lote.
        items = [c["props"]["item_id"] for c in componentes if c["tipo"] == "PropuestaCambio"]
        assert len(items) == len(set(items))

    async def test_al_modelo_le_llegan_80_renglones_y_1000_caracteres_y_no_puede_proponer_el_81(
        self, monkeypatch, record_property
    ):
        caso = _fixture("ADV-17")
        intento = _intento(caso, "kit_prompt_acotado")
        esperado = intento["condicion_exito"]
        doble = _modelo(monkeypatch, intento)
        kit = _kit_de_cuadernos(caso["kit"]["renglones"])

        cuerpo, res = await nl2c_flujo.proponer_en_kit(_texto(intento), kit, PADRE, "t-adv17")

        record_property("llamadas_al_modelo", doble.llamadas)
        usuario = doble.vistos[0]["usuario"]
        padre = usuario.split("<texto_del_padre>\n", 1)[1].split("\n</texto_del_padre>", 1)[0]
        assert len(padre) <= esperado["max_caracteres_del_padre"]
        assert re.search(rf"^L{esperado['max_lineas_en_prompt']} \|", usuario, re.M)
        assert not re.search(rf"^L{esperado['max_lineas_en_prompt'] + 1} \|", usuario, re.M)
        assert cuerpo["estado"] == esperado["estado"]
        assert res.rechazadas == esperado["rechazadas"]

    async def test_por_la_ruta_la_avalancha_tampoco_pasa_el_tope(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        caso = _fixture("ADV-17")
        intento = _intento(caso, "kit_avalancha")
        tid = await sembrar(motor)
        doble = _modelo(monkeypatch, intento)

        async def ver_grande(_motor, _id, **_kw):  # noqa: ANN001
            return {"kits": [_kit_de_cuadernos(caso["kit"]["renglones"])]}

        monkeypatch.setattr(trabajos, "ver", ver_grande)
        r = await _pedir(cliente, intento, tid)

        record_property("llamadas_al_modelo", doble.llamadas)
        cuerpo = r.json()
        assert r.status_code == 200 and doble.llamadas == 1
        assert len(cuerpo["ui"]["componentes"]) <= intento["condicion_exito"]["max_componentes"]
        assert _la_web_la_pinta(cuerpo["ui"]) == []
        assert cuerpo["contexto"] == {"accion": "mas_barato", "categoria": "cuadernos"}


class ProveedorDelAsistente:
    """El `urlopen` del adaptador real (`nl2c._llamar_gemini`), sin red: guarda el pedido y contesta."""

    def __init__(self, respuesta: dict[str, Any]) -> None:
        self.respuesta = respuesta
        self.pedidos: list[dict[str, Any]] = []

    def __call__(self, pedido: urllib.request.Request, timeout: float | None = None):  # noqa: ANN204
        self.pedidos.append({"cuerpo": json.loads(pedido.data), "timeout": timeout})
        if "error" in self.respuesta:
            raise TimeoutError("The read operation timed out")
        return _RespuestaHttp(json.dumps(self.respuesta).encode())


class _RespuestaHttp(io.BytesIO):
    def __enter__(self) -> _RespuestaHttp:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def _proveedor(monkeypatch: pytest.MonkeyPatch, intento: dict[str, Any]) -> ProveedorDelAsistente:
    falso = ProveedorDelAsistente(intento["respuesta_proveedor"])
    # La clave es de mentira y `_LLAMAR` vuelve al adaptador real; la red no se toca.
    monkeypatch.setattr(gemini, "_clave_y_modelo", lambda: ("clave-de-mentira", gemini.MODELO_POR_DEFECTO))
    monkeypatch.setattr(urllib.request, "urlopen", falso)
    monkeypatch.setattr(nl2c, "_LLAMAR", nl2c._llamar_gemini)
    return falso


@pytest.mark.nfr("NFR-SEG-03")
class TestADV18ConsumoDelModelo:
    """LLM10: cuantas llamadas al modelo cuesta cada peticion, y que pasa si el modelo no contesta."""

    async def test_un_pedido_es_una_llamada_aunque_el_texto_pida_reintentar(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        intento = _intento(_fixture("ADV-18"), "un_turno")
        tid = await sembrar(motor)
        doble = _modelo(monkeypatch, intento)

        r = await _pedir(cliente, intento, tid)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert r.status_code == intento["condicion_exito"]["http"]
        assert doble.llamadas == intento["condicion_exito"]["llamadas_al_modelo"]
        assert r.json()["tokens"] == {"entrada": 860, "salida": 20}

    @pytest.mark.parametrize(
        ("intento_id", "ruta", "estado_kit", "con_sesion"),
        [
            ("ayuda_sin_modelo", "proponer", EstadoTrabajo.PUBLICADO.value, True),
            ("texto_de_4001", "interpretar", EstadoTrabajo.PUBLICADO.value, True),
            ("texto_de_4001", "proponer", EstadoTrabajo.PUBLICADO.value, True),
            ("sin_sesion", "proponer", EstadoTrabajo.PUBLICADO.value, False),
            ("kit_no_publicado", "proponer", EstadoTrabajo.ESPERA_REVISION.value, True),
        ],
    )
    async def test_lo_que_se_resuelve_sin_el_modelo_no_le_cuesta_ninguna_llamada(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        intento_id,
        ruta,
        estado_kit,
        con_sesion,
        record_property,
    ):
        intento = _intento(_fixture("ADV-18"), intento_id)
        esperado = intento["condicion_exito"]
        tid = await sembrar(motor, estado=estado_kit)
        doble = _modelo(monkeypatch, intento)

        r = await _pedir(cliente, intento, tid, ruta=ruta, headers=H if con_sesion else None)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert r.status_code == esperado["http"], r.json()
        assert doble.llamadas == 0
        if "estado" in esperado:
            assert r.json()["estado"] == esperado["estado"]
        if "error" in esperado:
            assert r.json()["error"] == esperado["error"]
        # El 400 no repite lo que se envio.
        assert "aaaa" not in r.text

    @pytest.mark.parametrize("ruta", ["interpretar", "proponer"])
    async def test_un_modelo_lento_da_503_despues_de_una_sola_llamada(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        ruta,
        record_property,
    ):
        intento = _intento(_fixture("ADV-18"), "modelo_lento")
        plazo = intento["respuesta_modelo"]
        tid = await sembrar(motor)
        doble = _modelo(monkeypatch, intento, demora=plazo["demora_segundos"])
        # `consultar_modelo` espera ESPERA_MODELO_SEGUNDOS + 2: se acorta a 0,1 s para no esperar 14 s.
        monkeypatch.setattr(nl2c, "ESPERA_MODELO_SEGUNDOS", plazo["plazo_segundos_en_la_prueba"] - 2)

        r = await _pedir(cliente, intento, tid, ruta=ruta)

        record_property("llamadas_al_modelo", doble.llamadas)
        assert r.status_code == intento["condicion_exito"]["http"]
        assert r.json()["error"] == intento["condicion_exito"]["error"]
        assert doble.llamadas == intento["condicion_exito"]["llamadas_al_modelo"]
        # La espera del hilo termina despues de la respuesta: se le da tiempo y se cuenta de nuevo.
        time.sleep(plazo["demora_segundos"])
        assert doble.llamadas == 1
        evento = "interpretar_sin_servicio" if ruta == "interpretar" else "proponer_sin_servicio"
        assert [e["motivo"] for e in nl2c.BITACORA if e["evento"] == evento] == ["tiempo agotado"]

    async def test_el_adaptador_real_pide_400_tokens_un_plazo_y_solo_las_funciones_del_kit(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        record_property,
    ):
        intento = _intento(_fixture("ADV-18"), "adaptador_con_tope")
        esperado = intento["condicion_exito"]
        tid = await sembrar(motor)
        proveedor = _proveedor(monkeypatch, intento)

        cuerpo = (await _pedir(cliente, intento, tid)).json()

        record_property("llamadas_al_modelo", len(proveedor.pedidos))
        (pedido,) = proveedor.pedidos
        assert len(proveedor.pedidos) == esperado["pedidos_al_proveedor"]
        assert pedido["cuerpo"]["generationConfig"]["maxOutputTokens"] == esperado["max_tokens_salida"]
        assert pedido["timeout"] == esperado["plazo_segundos"]
        llamado = pedido["cuerpo"]["toolConfig"]["functionCallingConfig"]
        assert llamado["mode"] == "ANY" and set(llamado["allowedFunctionNames"]) == nl2c.HERRAMIENTAS_KIT
        declaradas = {d["name"] for d in pedido["cuerpo"]["tools"][0]["functionDeclarations"]}
        assert declaradas == nl2c.HERRAMIENTAS_KIT
        assert cuerpo["estado"] == esperado["estado"]
        assert [c["tipo"] for c in cuerpo["ui"]["componentes"]] == esperado["tipos"]
        assert cuerpo["tokens"] == esperado["tokens"]
        assert "4111111111111111" not in json.dumps(cuerpo)

    @pytest.mark.parametrize("ruta", ["interpretar", "proponer"])
    async def test_el_adaptador_real_no_reintenta_si_el_proveedor_no_contesta(
        self,
        cliente,  # noqa: F811
        motor,
        monkeypatch,
        ruta,
        record_property,
    ):
        intento = _intento(_fixture("ADV-18"), "adaptador_sin_reintento")
        tid = await sembrar(motor)
        proveedor = _proveedor(monkeypatch, intento)

        r = await _pedir(cliente, intento, tid, ruta=ruta)

        record_property("llamadas_al_modelo", len(proveedor.pedidos))
        assert r.status_code == intento["condicion_exito"]["http"]
        assert r.json()["error"] == intento["condicion_exito"]["error"]
        assert len(proveedor.pedidos) == intento["condicion_exito"]["pedidos_al_proveedor"]
