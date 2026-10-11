"""La ruta rapida del acudiente sobre una lista revisada de la curaduria: aplicar, ver, comprar y pagar.

`make curaduria-importar` carga las listas revisadas de `datos/curaduria/` (N-85) y el poller y el
trabajador arman con cada una el kit canonico de su (colegio, grado). El acudiente que encuentra su
grado en `GET /v1/grados-canonicos` no sube nada: elige perfil y personaje y
`POST /v1/trabajos/aplicar-canonico` le crea un trabajo `parent_apply` que apunta al canonico y
congela el pedido en la bandeja (`trabajos.aplicar_canonico`).

Se usa un colegio de la curaduria que no es el Agustiniano (N-85) y, de sus grados, aquel cuyo
Ahorrador tiene mas lineas en las anclas del personaje (`optimizador.CONCEPTOS_ANCLA`), para que el
Fan cambie algo. Desde ADR 0030 (efb0827) el canonico trae Ahorrador y Premium y el Fan se arma para
quien pide un personaje. Sin canonico la prueba falla, no se salta (H-C-03).

Lo que hoy no cumple queda como `xfail(strict=True)` con su hallazgo: H-A-63.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from e2e_flujo import PERFILES_CON_PERSONAJE, lineas, registrar_acudiente
from sqlalchemy import text
from stack_vivo import ENTREGA_FICTICIA, conexion_a
from tukit_inteligencia.optimizador import CONCEPTOS_ANCLA

# Los colegios de `datos/curaduria/` con listas revisadas, salvo el Agustiniano (N-85).
COLEGIOS_DE_LA_CURADURIA = {
    "2030c794-3ff4-5b1a-a2ec-5c5d383de3f1": "Bahia Solano",
    "4c06f0e5-cb44-5865-93e5-ea7b2f115d49": "San Pedro",
}
PERFIL = "Fan"


def _por_item(kit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {linea["item_id"]: linea for linea in kit["lineas"]}


def _anclas(kit: dict[str, Any]) -> set[str]:
    return {linea.get("concepto") for linea in kit["lineas"] if not linea["informativa"]} & set(
        CONCEPTOS_ANCLA
    )


def _por_sku(linea: dict[str, Any]) -> tuple:
    return linea["sku"], linea["cantidad"], linea["precio_unitario"]


def _comprables(lineas_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lo mismo que `trabajos.ordenar` manda a comercio: sin lo informativo ni lo que no tiene precio."""
    return sorted(
        (
            {
                "sku": elegido["sku"],
                "nombre": elegido["nombre"],
                "cantidad": linea["unidades_a_comprar"],
                "precio_unitario": elegido["precio"],
            }
            for linea in lineas_
            if not linea["informativa"]
            and (elegido := linea.get("producto_elegido"))
            and elegido["precio"] is not None
        ),
        key=_por_sku,
    )


async def _lo_guardado(trabajo_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """La fila del trabajo y los `pedido_solicitado` que dejo en la bandeja de inteligencia."""
    async with conexion_a("inteligencia") as conexion:
        trabajo = (
            await conexion.execute(
                text(
                    "select estado, origen, usuario_id::text, hijos from trabajo_pipeline "
                    "where id = cast(:t as uuid)"
                ),
                {"t": trabajo_id},
            )
        ).one()
        pedidos = (
            await conexion.execute(
                text(
                    "select carga from bandeja_salida where tipo = 'pedido_solicitado' "
                    "and agregado_tipo = 'trabajo_pipeline' and agregado_id = cast(:t as uuid)"
                ),
                {"t": trabajo_id},
            )
        ).scalars()
        return dict(trabajo._mapping), list(pedidos)


@pytest.fixture(scope="module")
def canonico(http_flujo: httpx.Client) -> dict[str, Any]:
    """El grado de la curaduria cuyo Ahorrador canonico tiene mas anclas, y el personaje que las cubre."""
    grados = []
    for colegio_id in COLEGIOS_DE_LA_CURADURIA:
        respuesta = http_flujo.get("/v1/grados-canonicos", params={"colegio_id": colegio_id})
        assert respuesta.status_code == 200, respuesta.text
        grados += respuesta.json()["grados"]
    if not grados:
        pytest.fail(
            "ningun colegio de la curaduria tiene kit canonico: falta `make curaduria-importar` "
            "o que el poller y el trabajador armen sus kits"
        )

    candidatos = []
    for grado in grados:
        vista = http_flujo.get(f"/v1/trabajos/{grado['trabajo_id']}")
        assert vista.status_code == 200, vista.text
        kits = {k["perfil"]: k for k in vista.json()["kits"]}
        if "Ahorrador" in kits:
            candidatos.append((len(_anclas(kits["Ahorrador"])), grado["grado"], grado, kits))
    if not candidatos:
        pytest.fail(f"ningun kit canonico de la curaduria trae Ahorrador: {grados}")
    _, _, grado, kits = max(candidatos, key=lambda c: (c[0], c[1]))

    anclas = _anclas(kits["Ahorrador"])
    respuesta = http_flujo.get("/v1/catalogo/personajes")
    assert respuesta.status_code == 200, respuesta.text
    personajes = sorted(
        respuesta.json()["personajes"],
        key=lambda p: (-len(anclas & set(p["conceptos"])), -p["productos"], p["nombre"]),
    )
    if not personajes or not anclas & set(personajes[0]["conceptos"]):
        pytest.fail(f"ningun personaje del catalogo cubre las anclas {sorted(anclas)} del canonico")
    return {**grado, "kits": kits, "anclas": anclas, "personaje": personajes[0]["nombre"]}


@pytest.fixture(scope="module")
def aplicado(http_flujo: httpx.Client, canonico: dict[str, Any]) -> dict[str, Any]:
    """Un acudiente ficticio del colegio y grado del canonico aplica el Fan con el personaje."""
    acudiente = registrar_acudiente(http_flujo, canonico["colegio_id"], canonico["grado"])
    respuesta = http_flujo.post(
        "/v1/trabajos/aplicar-canonico",
        headers=acudiente["cabecera"],
        json={
            "colegio_id": canonico["colegio_id"],
            "grado": canonico["grado"],
            "anio_lectivo": canonico["anio_lectivo"],
            "perfil": PERFIL,
            "personaje": canonico["personaje"],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    vista = http_flujo.get(f"/v1/trabajos/{creado['trabajo_id']}", headers=acudiente["cabecera"])
    assert vista.status_code == 200, vista.text
    trabajo, pedidos = asyncio.run(_lo_guardado(creado["trabajo_id"]))
    return {
        "acudiente": acudiente,
        "creado": creado,
        "vista": vista.json(),
        "trabajo": trabajo,
        "pedidos": pedidos,
    }


@pytest.mark.nfr("NFR-PRE-02")
class TestElKitDeLaRutaRapida:
    def test_el_acudiente_ve_los_tres_kits_y_el_que_eligio_recomendado(
        self, aplicado, canonico, record_property
    ):
        vista = aplicado["vista"]
        record_property("colegio", COLEGIOS_DE_LA_CURADURIA[canonico["colegio_id"]])
        record_property("grado", canonico["grado"])
        record_property("personaje", canonico["personaje"])
        record_property("anclas", ",".join(sorted(canonico["anclas"])))

        assert (vista["estado"], vista["origen"], vista["error"]) == ("publicado", "parent_apply", None)
        assert [k["perfil"] for k in vista["kits"]] == list(PERFILES_CON_PERSONAJE)
        assert vista["recomendado"]["perfil"] == PERFIL
        assert vista["recomendado"]["razon"].strip()
        assert all(k["total"] > 0 for k in vista["kits"])

    def test_el_trabajo_apunta_al_canonico_de_la_lista_revisada(self, aplicado, canonico):
        trabajo, acudiente = aplicado["trabajo"], aplicado["acudiente"]

        assert (trabajo["estado"], trabajo["origen"], trabajo["usuario_id"]) == (
            "publicado",
            "parent_apply",
            acudiente["usuario_id"],
        )
        assert trabajo["hijos"] == [
            {
                "colegio_id": canonico["colegio_id"],
                "grado": canonico["grado"],
                "anio_lectivo": canonico["anio_lectivo"],
                "canonico_trabajo_id": canonico["trabajo_id"],
                "perfil": PERFIL,
                "personaje": canonico["personaje"],
            }
        ]

    def test_el_acudiente_lo_ve_entre_sus_solicitudes(self, http_flujo, aplicado):
        acudiente = aplicado["acudiente"]

        mias = http_flujo.get("/v1/trabajos", headers=acudiente["cabecera"])
        anonimo = http_flujo.get("/v1/trabajos")

        assert mias.status_code == 200, mias.text
        # El acudiente es nuevo: su unica solicitud es la de la ruta rapida.
        assert [t["trabajo_id"] for t in mias.json()["trabajos"]] == [aplicado["creado"]["trabajo_id"]]
        assert anonimo.status_code == 401

    def test_cada_kit_conserva_los_renglones_del_canonico(self, aplicado, canonico):
        renglones = set(_por_item(canonico["kits"]["Ahorrador"]))

        for kit in aplicado["vista"]["kits"]:
            assert set(_por_item(kit)) == renglones, kit["perfil"]
        for perfil in ("Ahorrador", "Premium"):
            aplicado_ = next(k for k in aplicado["vista"]["kits"] if k["perfil"] == perfil)
            assert aplicado_["total"] == canonico["kits"][perfil]["total"], perfil

    def test_el_fan_es_el_ahorrador_con_el_personaje_en_las_anclas(self, aplicado, canonico, record_property):
        base = _por_item(canonico["kits"]["Ahorrador"])
        fan = _por_item(next(k for k in aplicado["vista"]["kits"] if k["perfil"] == PERFIL))

        cambiadas = {
            item: linea
            for item, linea in fan.items()
            if linea.get("producto_elegido") != base[item].get("producto_elegido")
        }
        record_property("lineas_con_personaje", len(cambiadas))
        assert cambiadas
        assert {linea.get("concepto") for linea in cambiadas.values()} <= set(CONCEPTOS_ANCLA)
        assert {linea["producto_elegido"]["personaje"].casefold() for linea in cambiadas.values()} == {
            canonico["personaje"].casefold()
        }


@pytest.mark.nfr("NFR-PRE-03")
class TestNingunProductoFueraDelCatalogo:
    def test_ningun_sku_de_los_kits_ni_del_pedido_sale_de_fuera_del_catalogo(
        self, aplicado, catalogo, record_property
    ):
        skus = [
            sku
            for _, linea in lineas(aplicado["vista"])
            for sku in [(linea.get("producto_elegido") or {}).get("sku")]
            + [a["sku"] for a in linea["alternativas"]]
            if sku
        ] + [
            linea["producto_elegido"]["sku"]
            for pedido in aplicado["pedidos"]
            for linea in pedido["lineas"]
            if linea.get("producto_elegido")
        ]

        fuera = sorted(set(skus) - catalogo["skus"])
        record_property("skus_revisados", len(skus))
        record_property("skus_fuera_del_catalogo", len(fuera))
        assert skus
        assert fuera == []


@pytest.mark.nfr("NFR-PRE-04")
class TestLoQueElCanonicoNoTiene:
    # `raises=AssertionError`: si el canonico ya no trae un renglon ancla sin producto, la prueba
    # se cae en su precondicion (`pytest.fail`) como falla de verdad, no como el `xfail`.
    @pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=(
            "H-A-63: el Fan de la ruta rapida le pone el producto del personaje a un renglon ancla "
            "que el canonico dejo sin producto (HUECO_CATALOGO) y lo cobra"
        ),
    )
    def test_el_personaje_no_llena_un_renglon_que_el_canonico_dejo_sin_producto(
        self, aplicado, canonico, record_property
    ):
        base = _por_item(canonico["kits"]["Ahorrador"])
        fan = _por_item(next(k for k in aplicado["vista"]["kits"] if k["perfil"] == PERFIL))
        congelado = {linea["item_id"]: linea for linea in aplicado["pedidos"][0]["lineas"]}
        huecos = sorted(
            item
            for item, linea in base.items()
            if not linea["informativa"]
            and not linea.get("producto_elegido")
            and linea.get("concepto") in canonico["anclas"]
        )
        if not huecos:
            pytest.fail(f"el canonico {canonico['trabajo_id']} ya no trae renglones ancla sin producto")

        llenados = {
            base[item]["orden"]: {
                "estado_resolucion": base[item]["estado_resolucion"],
                "fan": (fan[item].get("producto_elegido") or {}).get("sku"),
                "pedido": (congelado[item].get("producto_elegido") or {}).get("sku"),
                "subtotal_pedido": congelado[item].get("subtotal_linea"),
            }
            for item in huecos
            if fan[item].get("producto_elegido") or congelado[item].get("producto_elegido")
        }
        record_property("huecos_ancla", ",".join(str(base[i]["orden"]) for i in huecos))
        record_property("huecos_llenados", repr(llenados))
        assert llenados == {}


@pytest.mark.nfr("NFR-PRE-06")
class TestElPedidoCongelado:
    def test_el_pedido_congelado_suma_sus_lineas(self, aplicado, canonico, record_property):
        assert len(aplicado["pedidos"]) == 1
        pedido = aplicado["pedidos"][0]
        fan = next(k for k in aplicado["vista"]["kits"] if k["perfil"] == PERFIL)
        con_precio = [
            linea
            for linea in pedido["lineas"]
            if not linea["informativa"] and (linea.get("producto_elegido") or {}).get("precio") is not None
        ]
        suma = sum(linea["subtotal_linea"] for linea in con_precio)
        record_property("total_cop", pedido["total_cop"])
        record_property("lineas_con_precio", len(con_precio))

        assert all(
            linea["subtotal_linea"] == linea["producto_elegido"]["precio"] * linea["unidades_a_comprar"]
            for linea in con_precio
        )
        assert (pedido["total_cop"], aplicado["creado"]["total"], fan["total"]) == (suma, suma, suma)
        assert {clave: pedido[clave] for clave in ("trabajo_id", "canonico_trabajo_id", "usuario_id")} == {
            "trabajo_id": aplicado["creado"]["trabajo_id"],
            "canonico_trabajo_id": canonico["trabajo_id"],
            "usuario_id": aplicado["acudiente"]["usuario_id"],
        }
        assert (pedido["perfil"], pedido["personaje"]) == (PERFIL, canonico["personaje"])

    def test_el_pago_aprobado_cobra_y_deja_pagado_el_pedido_congelado(
        self, http_flujo, aplicado, record_property
    ):
        from tukit_comercio.pasarela import PasarelaFalsa

        acudiente, pedido = aplicado["acudiente"], aplicado["pedidos"][0]
        trabajo_id = aplicado["creado"]["trabajo_id"]

        orden = http_flujo.post(
            f"/v1/trabajos/{trabajo_id}/ordenar",
            headers=acudiente["cabecera"],
            json={"perfil": PERFIL, "correo": acudiente["correo"], "entrega": ENTREGA_FICTICIA},
        )
        assert orden.status_code == 201, orden.text
        datos = orden.json()
        assert (datos["estado"], datos["total"]) == ("iniciado", pedido["total_cop"])
        evento = PasarelaFalsa().emitir_evento(
            referencia=datos["referencia_wompi"],
            transaccion_id=datos["transaccion_wompi"],
            estado_wompi="APPROVED",
            monto_centavos=datos["total"] * 100,
        )
        webhook = http_flujo.post("/v1/webhooks/wompi", json=evento)
        assert webhook.status_code == 200, webhook.text
        assert webhook.json()["pedido_transicionado"] is True
        pagada = http_flujo.get(
            f"/v1/comercio/mis-pedidos/{datos['pedido_id']}", headers=acudiente["cabecera"]
        )
        assert pagada.status_code == 200, pagada.text

        cuerpo = pagada.json()
        record_property("pedido_id", datos["pedido_id"])
        record_property("total", cuerpo["total"])
        record_property("lineas_pagadas", len(cuerpo["lineas"]))
        assert (cuerpo["estado"], cuerpo["trabajo_id"], cuerpo["total"]) == (
            "pagado",
            trabajo_id,
            pedido["total_cop"],
        )
        assert cuerpo["lineas"]
        assert sorted(cuerpo["lineas"], key=_por_sku) == _comprables(pedido["lineas"])
