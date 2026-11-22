"""El flujo del colegio: onboarding de la lista, kit por la ruta lenta, cola de revision.

Un administrador sube la lista de un colegio nuevo (`/v1/admin/onboarding`) y,
antes de que nadie la revise, se pide un kit para ese colegio y grado
(`POST /v1/trabajos`). Como la version vigente no esta revisada, el pipeline
toma la ruta LENTA: emparejar cada renglon contra el catalogo y optimizar. El
trabajo termina en la cola de revision: el acudiente no ve kits y el
administrador si.

Aqui se mide lo que la ruta lenta hace con G01 sobre el catalogo vivo:

- NFR-REN-03: cada sondeo de `GET /v1/trabajos/{id}` trae las cuatro etapas y su avance;
- NFR-PRE-02: cada linea vuelve a su renglon y el top-1 contra el oro se reporta;
- NFR-PRE-03: ningun producto del kit sale de fuera del catalogo;
- NFR-PRE-04: lo informativo no se compra y los huecos dicen por que.

Ademas se previsualiza la misma version (`/v1/admin/onboarding/{v}/preview`)
y se compara renglon por renglon con el kit.

Lo que hoy no cumple queda como `xfail(strict=True)` con su hallazgo:
H-A-37, H-A-39 y H-A-45.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from e2e_flujo import (
    ANIO_LECTIVO,
    ETAPAS,
    PERFILES,
    archivo,
    lineas,
    ordenes,
    por_orden,
    productos_de_los_kits,
    sondear,
)
from stack_vivo import ENTREGA_FICTICIA

HUECOS = ("SIN_MATCH", "HUECO_CATALOGO", "ABSTENCION")


@pytest.fixture(scope="module")
def grado(http_flujo: httpx.Client, admin: dict[str, str]) -> dict[str, Any]:
    """G01 subida por onboarding a un colegio nuevo, y un kit pedido sobre ella sin revisarla."""
    colegio_id = str(uuid.uuid4())
    onboarding = http_flujo.post(
        "/v1/admin/onboarding",
        headers=admin,
        data={"colegio_id": colegio_id, "grado": "Tercero", "anio_lectivo": str(ANIO_LECTIVO)},
        files={"archivo": archivo("G01")},
    )
    assert onboarding.status_code == 200, onboarding.text
    pedido = http_flujo.post(
        "/v1/trabajos",
        json={
            "hijos": [
                {
                    "referencia": "hijo-1",
                    "colegio_id": colegio_id,
                    "grado": "Tercero",
                    "anio_lectivo": ANIO_LECTIVO,
                }
            ]
        },
    )
    assert pedido.status_code == 202, pedido.text
    trabajo_id = pedido.json()["trabajo_id"]
    sondeos = sondear(http_flujo, trabajo_id)
    vista_admin = http_flujo.get(f"/v1/admin/trabajos/{trabajo_id}", headers=admin)
    assert vista_admin.status_code == 200, vista_admin.text
    return {
        "colegio_id": colegio_id,
        "onboarding": onboarding.json(),
        "trabajo_id": trabajo_id,
        "sondeos": sondeos,
        "vista": sondeos[-1],
        "admin": vista_admin.json(),
    }


def _por_orden(vista: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {linea["orden"]: linea for linea in vista["kits"][0]["lineas"]}


def _resumen(linea: dict[str, Any]) -> tuple:
    return (
        linea["tipo"],
        linea["informativa"],
        linea["estado_resolucion"],
        linea["cantidad_pedida"],
        (linea.get("producto_elegido") or {}).get("sku"),
    )


_DISPONIBLE_EN_CASA = pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-45: `GET /v1/listas/{id}` le pone al renglon el `tipo_item` de su concepto (libro_libre) y "
        "el parseo ya no lo detecta: «el disponible en casa» sale como libro a comprar, no informativo"
    ),
)


def _informativo(orden: int):
    texto = por_orden("G01")[orden]["texto"]
    return pytest.param(orden, id=str(orden), marks=[_DISPONIBLE_EN_CASA] if "en casa" in texto else [])


@pytest.fixture(scope="module")
def preview(http_flujo: httpx.Client, admin: dict[str, str], grado: dict[str, Any]) -> dict[str, Any]:
    """Lo que el administrador ve al previsualizar la misma version antes de aprobarla."""
    version_id = grado["onboarding"]["version_id"]
    respuesta = http_flujo.post(
        f"/v1/admin/onboarding/{version_id}/preview",
        headers=admin,
        json={"colegio_id": grado["colegio_id"], "grado": "Tercero", "anio_lectivo": ANIO_LECTIVO},
    )
    assert respuesta.status_code == 200, respuesta.text
    vista = http_flujo.get(f"/v1/admin/trabajos/{respuesta.json()['trabajo_id']}", headers=admin)
    assert vista.status_code == 200, vista.text
    return vista.json()


class TestElTrabajoDelGrado:
    def test_el_onboarding_importa_los_dieciocho_renglones(self, grado):
        assert grado["onboarding"]["grado"] == "Tercero"
        assert grado["onboarding"]["items"] == len(por_orden("G01"))

    @pytest.mark.nfr("NFR-REN-03")
    def test_cada_sondeo_trae_la_etapa_y_el_avance(self, grado, record_property):
        sondeos = grado["sondeos"]

        sin_etapa = [
            n
            for n, sondeo in enumerate(sondeos)
            if [e["nombre"] for e in sondeo["etapas"]] != list(ETAPAS)
            or any(not e["estado"] for e in sondeo["etapas"])
        ]
        avances = [sum(e["estado"] != "pendiente" for e in s["etapas"]) for s in sondeos]
        recorrido = []
        for sondeo, avance in zip(sondeos, avances, strict=True):
            paso = f"{sondeo['estado']}:{avance}/{len(ETAPAS)}"
            if not recorrido or recorrido[-1] != paso:
                recorrido.append(paso)
        record_property("sondeos", len(sondeos))
        record_property("sondeos_sin_etapa", len(sin_etapa))
        record_property(
            "porcentaje_con_etapa", round(100 * (len(sondeos) - len(sin_etapa)) / len(sondeos), 2)
        )
        record_property("recorrido", " > ".join(recorrido))
        record_property("ms_por_etapa", ",".join(f"{e['nombre']}={e['ms']}" for e in sondeos[-1]["etapas"]))
        assert sin_etapa == []
        assert avances == sorted(avances), "el avance retrocedio entre dos sondeos"
        assert avances[-1] == len(ETAPAS)

    def test_queda_en_revision_y_el_acudiente_no_ve_kits(self, grado):
        vista = grado["vista"]

        assert (vista["estado"], vista["origen"], vista["error"]) == (
            "espera_revision",
            "colegio_grado",
            None,
        )
        assert vista["kits"] == []
        assert vista["etapas"][2]["detalle"]["a_revision"] > 0

    def test_el_administrador_ve_los_tres_kits(self, grado):
        vista = grado["admin"]

        assert [k["perfil"] for k in vista["kits"]] == list(PERFILES)
        assert vista["recomendado"]["perfil"] in PERFILES
        assert vista["lineas_pendientes"]


@pytest.mark.nfr("NFR-PRE-02")
class TestLaRutaLentaContraElOro:
    def test_cada_linea_vuelve_a_su_renglon(self, grado, record_property):
        renglones = por_orden("G01")

        sin_origen = [
            (kit["perfil"], linea["orden"])
            for kit, linea in lineas(grado["admin"])
            if linea["orden"] not in renglones or linea["descripcion"] != renglones[linea["orden"]]["texto"]
        ]
        record_property("lineas_sin_origen", len(sin_origen))
        assert sin_origen == []
        for kit in grado["admin"]["kits"]:
            assert sorted(linea["orden"] for linea in kit["lineas"]) == sorted(renglones)

    def test_el_top1_contra_el_oro_se_reporta(self, grado, record_property):
        renglones = por_orden("G01")
        reconocibles = ordenes("G01", "exacto") | ordenes("G01", "facil")
        kit = _por_orden(grado["admin"])

        concepto = [
            o for o in reconocibles if kit[o].get("concepto") == renglones[o]["emparejamiento"]["concepto"]
        ]
        con_producto = [o for o in concepto if kit[o]["estado_resolucion"] == "RESUELTO_AUTO"]
        record_property("reconocibles", len(reconocibles))
        record_property("top1_concepto", len(concepto))
        record_property("top1_con_producto", len(con_producto))
        record_property("top1_tasa", round(len(con_producto) / len(reconocibles), 4))
        record_property("estados", ",".join(f"{o}:{kit[o]['estado_resolucion']}" for o in sorted(kit)))
        assert len(concepto) == len(reconocibles)

    def test_lo_que_el_oro_reconoce_sale_con_producto(self, grado, record_property):
        """No regresion de H-A-44: desde 6c29c83 el cargador del catalogo (el de `bd-sembrar`)
        guarda los atributos del CSV (`cargador.py:504`, `atributos_de_csv`)."""
        reconocibles = ordenes("G01", "exacto") | ordenes("G01", "facil")
        kit = _por_orden(grado["admin"])

        sin_producto = sorted(o for o in reconocibles if kit[o].get("producto_elegido") is None)
        record_property("reconocibles_sin_producto", ",".join(map(str, sin_producto)))
        assert sin_producto == []


@pytest.mark.nfr("NFR-PRE-03")
class TestNingunProductoFueraDelCatalogo:
    def test_ningun_sku_del_kit_ni_de_sus_alternativas_sale_de_fuera_del_catalogo(
        self, grado, catalogo, record_property
    ):
        skus = [
            sku
            for _, linea in lineas(grado["admin"])
            for sku in [(linea.get("producto_elegido") or {}).get("sku")]
            + [a["sku"] for a in linea["alternativas"]]
            if sku
        ]

        fuera = sorted(set(skus) - catalogo["skus"])
        record_property("skus_revisados", len(skus))
        record_property("skus_fuera_del_catalogo", len(fuera))
        assert skus
        assert fuera == []

    def test_ningun_producto_canonico_id_guardado_sale_de_fuera_del_catalogo(
        self, grado, catalogo, record_property
    ):
        filas = asyncio.run(productos_de_los_kits(grado["trabajo_id"]))

        con_producto = [f for f in filas if f[1] is not None]
        fuera = sorted({f[1] for f in con_producto} - catalogo["ids"])
        record_property("lineas_guardadas", len(filas))
        record_property("producto_canonico_id_fuera", len(fuera))
        assert con_producto
        assert fuera == []


@pytest.mark.nfr("NFR-PRE-04")
class TestLoQueNoSeCompra:
    @pytest.mark.parametrize("orden", [_informativo(o) for o in sorted(ordenes("G01", "informativo"))])
    def test_los_informativos_no_se_compran_y_dicen_que_hacer(self, orden, grado, record_property):
        esperado = por_orden("G01")[orden]["parseo"]

        linea = _por_orden(grado["admin"])[orden]

        record_property("tipo", linea["tipo"])
        record_property("estado_resolucion", linea["estado_resolucion"])
        assert (linea["tipo"], linea["informativa"]) == (esperado["tipo_item"], True)
        assert linea.get("producto_elegido") is None
        assert linea["cantidad_pedida"] == esperado["cantidad"]
        assert linea["mensaje"].strip()

    def test_los_huecos_no_traen_producto_y_dicen_por_que(self, grado, record_property):
        kit = _por_orden(grado["admin"])

        huecos = {o: kit[o] for o in ordenes("G01", "hueco")}
        record_property(
            "estados", ",".join(f"{o}:{h['estado_resolucion']}" for o, h in sorted(huecos.items()))
        )
        for linea in huecos.values():
            assert linea["estado_resolucion"] in HUECOS
            assert linea.get("producto_elegido") is None
            assert linea["mensaje"].strip()

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-39: `sustitutos` nunca se escribe: un hueco del catalogo no ofrece ninguna alternativa",
    )
    def test_los_huecos_ofrecen_una_alternativa(self, grado):
        kit = _por_orden(grado["admin"])

        assert all(kit[o]["alternativas"] for o in ordenes("G01", "hueco"))


@pytest.mark.nfr("NFR-PRE-02")
class TestElPreviewEsElKit:
    def test_el_preview_es_de_la_misma_version(self, preview, grado):
        assert preview["origen"] == "preview_onboarding"
        assert preview["estado"] == "espera_revision"
        assert (
            preview["etapas"][0]["detalle"]["listas"][0]["lista_id"]
            == (grado["admin"]["etapas"][0]["detalle"]["listas"][0]["lista_id"])
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-45: el preview lee la version por `revision()` (sin `tipo_item`) y el kit por `lista()` "
            "(con el `tipo_item` del concepto): el mismo renglon sale distinto en uno y otro"
        ),
    )
    def test_cada_renglon_sale_igual_en_el_preview_y_en_el_kit(self, preview, grado, record_property):
        en_preview = {o: _resumen(linea) for o, linea in _por_orden(preview).items()}
        en_kit = {o: _resumen(linea) for o, linea in _por_orden(grado["admin"]).items()}

        distintos = sorted(o for o in en_kit if en_preview.get(o) != en_kit[o])
        record_property("renglones_distintos", ",".join(map(str, distintos)))
        assert distintos == []


class TestLaColaDeRevision:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-37: `ordenar` no mira el estado del trabajo: un kit que espera revision se puede "
            "comprar (y sin sesion, H-C-06)"
        ),
    )
    def test_un_kit_que_espera_revision_no_se_puede_comprar(self, http_flujo, grado, record_property):
        orden = http_flujo.post(
            f"/v1/trabajos/{grado['trabajo_id']}/ordenar",
            json={
                "perfil": "Ahorrador",
                "correo": "qa-e2e-colegio@example.test",
                "entrega": ENTREGA_FICTICIA,
            },
        )

        record_property("codigo", orden.status_code)
        assert orden.status_code in (403, 409)

    def test_aprobar_el_kit_del_grado_lo_publica(self, http_flujo, admin, grado, record_property):
        """No regresion de H-A-01: desde c57c0b3 la migracion `20260928_1900_tabla_kit_canonico`
        crea `kit_canonico`."""
        respuesta = http_flujo.post(
            f"/v1/admin/trabajos/{grado['trabajo_id']}/revision", headers=admin, json={"decision": "aprobar"}
        )

        record_property("codigo", respuesta.status_code)
        record_property("cuerpo", respuesta.text[:200])
        assert respuesta.status_code == 200, respuesta.text
        assert http_flujo.get(f"/v1/trabajos/{grado['trabajo_id']}").json()["estado"] == "publicado"
