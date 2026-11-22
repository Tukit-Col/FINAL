"""El flujo del acudiente de punta a punta: registro, subida, revision, kit, orden y pago.

Es el flujo de `docs/FLUJO_EXTREMO_A_EXTREMO.md` para un padre cuyo colegio no
esta en Tukit: se registra, sube la foto de la lista (`/subir`), un
administrador la revisa y la aprueba, el poller del catalogo arma su kit por la
ruta rapida (`lista_verificada`) y el padre compra el que le recomiendan. Las
listas son los dorados de `datos/golden/`; lo que el modelo "lee" de cada una es
la respuesta grabada en `fixtures-modelo/` (ver `conftest.py`).

Cada paso se comprueba por su contenido, no por su codigo: que lo que llega al
catalogo es lo que dice la lista, que cada linea del kit vuelve a su renglon,
que ningun producto sale de fuera del catalogo y que la orden pagada tiene las
lineas del kit.

Lo que hoy no cumple queda como `xfail(strict=True)` con su hallazgo:
H-A-36, H-A-38, H-A-39, H-A-40, H-A-41, H-A-42, H-A-43 y H-A-62.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from e2e_flujo import (
    ACEPTADAS,
    ESPERADOS,
    PERFILES,
    cerrar,
    colegio_ficticio,
    esperar_trabajo_del_acudiente,
    lineas,
    ordenes,
    por_orden,
    productos_de_los_kits,
    quitar_concepto_sin_producto,
    registrar_acudiente,
    revision,
    subir,
)
from stack_vivo import ENTREGA_FICTICIA

# Los cuatro renglones que G05 escribe con confianza 0,41...0,55 (`datos/golden/README.md`).
# La percepcion no tiene umbral propio en FINAL: el corte de 0,6 es el del diseno del dorado.
BAJA_CONFIANZA = 0.6
RECHAZADAS = {"G04": "percepcion_fallida", "G08": "pagina_incompleta", "G10": "lista_de_varios_grados"}


@pytest.fixture(scope="module")
def acudiente(http_flujo: httpx.Client, colegio_aliado: str) -> dict[str, Any]:
    return registrar_acudiente(http_flujo, colegio_aliado)


@pytest.fixture(scope="module")
def subidas(http_flujo: httpx.Client, acudiente: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cada lista aceptada, subida por el mismo acudiente con un colegio escrito a mano distinto."""
    resultado = {}
    for variante in ACEPTADAS:
        respuesta = subir(http_flujo, acudiente["cabecera"], variante, colegio_ficticio(variante))
        assert respuesta.status_code == 202, f"{variante}: {respuesta.text}"
        cuerpo = respuesta.json()
        assert cuerpo["contacto_referencia"] == acudiente["usuario_id"]
        resultado[variante] = cuerpo["subidas"][0]
    return resultado


def _por_sku(linea: dict[str, Any]) -> tuple:
    return linea["sku"], linea["cantidad"], linea["precio_unitario"]


def _revision_y_percepcion(http: httpx.Client, admin: dict[str, str], version_id: str):
    percepcion = http.get(f"/v1/admin/listas/{version_id}/percepcion", headers=admin)
    assert percepcion.status_code == 200, percepcion.text
    return revision(http, admin, version_id), percepcion.json()


@pytest.mark.nfr("NFR-PRE-01")
class TestLaSubidaLlegaAlCatalogo:
    @pytest.mark.parametrize("variante", ACEPTADAS)
    def test_la_lista_aceptada_llega_renglon_por_renglon(
        self, variante, http_flujo, admin, subidas, record_property
    ):
        esperado = ESPERADOS[variante]
        subida = subidas[variante]

        vista, percepcion = _revision_y_percepcion(http_flujo, admin, subida["version_id"])

        assert subida["grado"] == vista["grado"] == esperado["grados"][0]
        assert vista["revisada"] is False
        assert vista["colegio_datos"]["nombre"].startswith(f"Colegio Ficticio QA {variante}")
        items = sorted(vista["items"], key=lambda i: i["orden"])
        record_property("variante", variante)
        record_property("filas_esperadas", len(esperado["items"]))
        record_property("filas_en_el_catalogo", len(items))
        assert [i["orden"] for i in items] == list(range(1, len(esperado["items"]) + 1))
        assert [i["texto_original"] for i in items] == [e["descripcion"] for e in esperado["items"]]
        assert [
            i["cantidad"] for i, e in zip(items, esperado["items"], strict=True) if e["cantidad"] is not None
        ] == [e["cantidad"] for e in esperado["items"] if e["cantidad"] is not None]
        assert [(p["texto_original"], p["confianza"]) for p in percepcion["items"]] == [
            (e["descripcion"], e["confianza"]) for e in esperado["items"]
        ]
        assert len(percepcion["paginas"]) == esperado["paginas"]

    @pytest.mark.parametrize("variante", sorted(RECHAZADAS))
    def test_la_lista_rechazada_no_llega_y_dice_por_que(
        self, variante, http_flujo, acudiente, record_property
    ):
        respuesta = subir(http_flujo, acudiente["cabecera"], variante, colegio_ficticio(variante))

        cuerpo = respuesta.json()
        record_property("variante", variante)
        record_property("codigo", respuesta.status_code)
        record_property("error", cuerpo.get("error"))
        assert respuesta.status_code == 422
        assert cuerpo["error"] == RECHAZADAS[variante] == ESPERADOS[variante]["error"]
        assert cuerpo["mensaje"].strip()
        # Nunca se le devuelve al cliente el contenido que subio, ni siquiera al rechazarlo.
        assert "subidas" not in cuerpo
        assert not any(i["descripcion"] in respuesta.text for i in ESPERADOS[variante]["items"])

    def test_varios_grados_dice_cuales_encontro(self, http_flujo, acudiente):
        respuesta = subir(http_flujo, acudiente["cabecera"], "G10", colegio_ficticio("G10"))

        assert respuesta.status_code == 422
        assert sorted(respuesta.json()["grados_detectados"]) == ESPERADOS["G10"]["grados"]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-36: sin el extra `pdf` de inteligencia (pypdfium2) el PDF de 41 paginas da "
            "pdf_ilegible y el tope de 40 paginas no llega a evaluarse"
        ),
    )
    def test_el_pdf_que_pasa_el_tope_se_rechaza_por_largo(self, http_flujo, acudiente, record_property):
        respuesta = subir(http_flujo, acudiente["cabecera"], "G02", colegio_ficticio("G02"))

        record_property("error", respuesta.json().get("error"))
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "archivo_demasiado_largo"


@pytest.mark.nfr("NFR-PRE-05")
class TestLaBajaConfianza:
    def test_la_confianza_de_cada_renglon_queda_guardada(self, http_flujo, admin, subidas, record_property):
        _, percepcion = _revision_y_percepcion(http_flujo, admin, subidas["G05"]["version_id"])

        bajas = [n for n, p in enumerate(percepcion["items"], start=1) if p["confianza"] < BAJA_CONFIANZA]
        record_property("renglones_baja_confianza", ",".join(map(str, bajas)))
        assert bajas == [2, 5, 8, 11]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-40: `requiere_revision` solo depende de que haya concepto; la confianza de la "
            "percepcion se guarda pero no manda ningun renglon a revision"
        ),
    )
    def test_los_renglones_de_baja_confianza_quedan_marcados_a_revision(
        self, http_flujo, admin, subidas, record_property
    ):
        vista, percepcion = _revision_y_percepcion(http_flujo, admin, subidas["G05"]["version_id"])
        confianza = {n: p["confianza"] for n, p in enumerate(percepcion["items"], start=1)}

        marcados = {i["orden"] for i in vista["items"] if i["requiere_revision"]}
        bajas = {n for n, c in confianza.items() if c < BAJA_CONFIANZA}
        record_property("marcados_a_revision", ",".join(map(str, sorted(marcados))))
        assert bajas <= marcados


class TestLaCantidadEscritaEnElTexto:
    @pytest.mark.nfr("NFR-PRE-01")
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-38: sin columna de cantidad, `_items_desde_percepcion` guarda 1 en vez de leer el "
            "numero que trae el texto («4 Cuaderno…»)"
        ),
    )
    def test_la_cantidad_del_texto_llega_al_catalogo(self, http_flujo, admin, subidas, record_property):
        vista = revision(http_flujo, admin, subidas["G06"]["version_id"])

        obtenidas = {i["orden"]: i["cantidad"] for i in vista["items"]}
        esperadas = {o: f["parseo"]["cantidad"] for o, f in por_orden("G06").items()}
        record_property("cantidades_distintas", sum(1 for o in esperadas if obtenidas.get(o) != esperadas[o]))
        assert obtenidas == esperadas


# ---------------------------------------------------------------- aprobar sin cambios


@pytest.fixture(scope="module")
def sin_cambios(http_flujo: httpx.Client, admin: dict[str, str], colegio_aliado: str) -> dict[str, Any]:
    """G01 aprobada tal como la clasifico el catalogo, sin tocar ningun renglon."""
    padre = registrar_acudiente(http_flujo, colegio_aliado)
    respuesta = subir(http_flujo, padre["cabecera"], "G01", colegio_ficticio("G01"))
    assert respuesta.status_code == 202, respuesta.text
    version_id = respuesta.json()["subidas"][0]["version_id"]
    cerrar(http_flujo, admin, version_id)
    return esperar_trabajo_del_acudiente(http_flujo, padre["cabecera"], version_id)


class TestAprobarLaListaSinCambios:
    @pytest.mark.nfr("NFR-PRE-04")
    def test_el_acudiente_recibe_sus_tres_kits(self, sin_cambios, record_property):
        """No regresion de H-A-41: desde b97ce00, en la ruta rapida un renglon cuyo concepto no
        tiene producto (C095) queda `HUECO_CATALOGO` (`trabajos.py:525-530`) y el trabajo se
        publica. Son dos kits y no tres por el ADR 0030 (efb0827); el nombre se conserva por
        la trazabilidad."""
        record_property("estado", sin_cambios["estado"])
        record_property("error", sin_cambios["error"])
        record_property("etapas", ",".join(f"{e['nombre']}:{e['estado']}" for e in sin_cambios["etapas"]))
        assert sin_cambios["estado"] == "publicado"
        assert [k["perfil"] for k in sin_cambios["kits"]] == list(PERFILES)


# ------------------------------------------------------- un trabajo que falla en la ruta rapida

# El catalogo guarda cualquier cantidad mayor que cero (`routers/admin.py:821-830`); con un
# millon en el renglon 1 el total del kit no cabe en `kit.total_cop` (integer) y el insert
# falla dentro de `procesar`. Desde b97ce00 el renglon sin producto ya no tumba el trabajo
# (H-A-41), asi que este es el disparador que queda para el manejador generico
# (`trabajos.py:981-991`).
CANTIDAD_DESBORDADA = 1_000_000


@pytest.fixture(scope="module")
def fallido(http_flujo: httpx.Client, admin: dict[str, str], colegio_aliado: str) -> dict[str, Any]:
    """G01 con un millon de unidades en el renglon 1, cerrada por el administrador."""
    padre = registrar_acudiente(http_flujo, colegio_aliado)
    respuesta = subir(http_flujo, padre["cabecera"], "G01", colegio_ficticio("G01"))
    assert respuesta.status_code == 202, respuesta.text
    version_id = respuesta.json()["subidas"][0]["version_id"]
    renglon = next(i for i in revision(http_flujo, admin, version_id)["items"] if i["orden"] == 1)
    edicion = http_flujo.patch(
        f"/v1/admin/listas/{version_id}/items/{renglon['item_id']}",
        headers=admin,
        json={"cantidad": CANTIDAD_DESBORDADA},
    )
    assert edicion.status_code == 200, edicion.text
    cerrar(http_flujo, admin, version_id)
    vista = esperar_trabajo_del_acudiente(http_flujo, padre["cabecera"], version_id)
    sin_sesion = http_flujo.get(f"/v1/trabajos/{vista['trabajo_id']}")
    return {**vista, "sin_sesion": sin_sesion.status_code}


class TestElTrabajoQueFalla:
    # Como H-A-35 (NFR-PRE-06): la cantidad no tiene tope antes de llegar al total.
    @pytest.mark.nfr("NFR-PRE-06")
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-62: el revisor puede guardar una cantidad de un millon y el total del kit desborda "
            "`kit.total_cop` (integer): el trabajo del acudiente queda fallido con `error_interno`"
        ),
    )
    def test_una_cantidad_que_el_revisor_guarda_no_tumba_el_trabajo(self, fallido, record_property):
        record_property("estado", fallido["estado"])
        record_property("error", fallido["error"])
        assert (fallido["estado"], fallido["error"]) != ("fallido", "error_interno")

    @pytest.mark.nfr("NFR-REN-03")
    # H-A-41: corregido en fix/hallazgos-qa; sale XPASS(strict) en la corrida del Mac y se quita el xfail.
    def test_si_falla_el_sondeo_dice_en_que_etapa(self, fallido, record_property):
        record_property("etapas", ",".join(f"{e['nombre']}:{e['estado']}" for e in fallido["etapas"]))
        assert fallido["estado"] == "fallido"
        assert any(e["estado"] not in ("pendiente", "ok") for e in fallido["etapas"])

    # H-A-43: corregido en fix/hallazgos-qa; sale XPASS(strict) en la corrida del Mac y se quita el xfail.
    def test_el_error_no_expone_la_base(self, fallido, record_property):
        mensaje = fallido["mensaje"] or ""
        record_property("mensaje_inicio", mensaje[:120])
        record_property("codigo_sin_sesion", fallido["sin_sesion"])
        assert fallido["estado"] == "fallido"
        assert not any(marca in mensaje for marca in ("INSERT INTO", "sqlalchemy", "asyncpg", "[parameters:"))


# ------------------------------------------------------- aprobar con la revision minima


@pytest.fixture(scope="module")
def corregido(
    http_flujo: httpx.Client, admin: dict[str, str], colegio_aliado: str, catalogo: dict[str, Any]
) -> dict[str, Any]:
    """G01 aprobada despues de quitarle el concepto a los renglones cuyo concepto no tiene producto."""
    padre = registrar_acudiente(http_flujo, colegio_aliado)
    respuesta = subir(http_flujo, padre["cabecera"], "G01", colegio_ficticio("G01"))
    assert respuesta.status_code == 202, respuesta.text
    version_id = respuesta.json()["subidas"][0]["version_id"]
    corregidos = quitar_concepto_sin_producto(http_flujo, admin, version_id, catalogo["sin_producto"])
    cerrar(http_flujo, admin, version_id)
    vista = esperar_trabajo_del_acudiente(http_flujo, padre["cabecera"], version_id)
    return {"padre": padre, "version_id": version_id, "corregidos": corregidos, "vista": vista}


@pytest.mark.nfr("NFR-PRE-02")
class TestElKitDelAcudiente:
    def test_la_revision_minima_solo_toca_el_renglon_sin_producto(self, corregido, record_property):
        record_property("renglones_corregidos", ",".join(map(str, corregido["corregidos"])))
        assert corregido["corregidos"] == [14]

    def test_el_acudiente_recibe_tres_kits_y_una_recomendacion(self, corregido):
        vista = corregido["vista"]

        assert (vista["estado"], vista["origen"], vista["error"]) == ("publicado", "lista_verificada", None)
        assert [k["perfil"] for k in vista["kits"]] == list(PERFILES)
        assert vista["recomendado"]["perfil"] in PERFILES
        assert vista["recomendado"]["razon"].strip()
        assert all(k["total"] > 0 for k in vista["kits"])
        assert [e["nombre"] for e in vista["etapas"]] == [
            "percepcion",
            "normalizacion",
            "resolucion",
            "optimizacion",
        ]
        assert all(e["estado"] == "ok" for e in vista["etapas"])
        assert vista["etapas"][2]["detalle"]["fuente"] == "lista_verificada"
        assert vista["etapas"][0]["detalle"]["listas"][0]["version_id"] == corregido["version_id"]

    def test_cada_linea_vuelve_a_su_renglon(self, corregido, record_property):
        renglones = por_orden("G01")

        sin_origen = [
            (kit["perfil"], linea["orden"])
            for kit, linea in lineas(corregido["vista"])
            if linea["hijo"] != "hijo-1"
            or linea["orden"] not in renglones
            or linea["descripcion"] != renglones[linea["orden"]]["texto"]
        ]
        record_property("lineas", sum(1 for _ in lineas(corregido["vista"])))
        record_property("lineas_sin_origen", len(sin_origen))
        assert sin_origen == []
        for kit in corregido["vista"]["kits"]:
            assert sorted(linea["orden"] for linea in kit["lineas"]) == sorted(renglones)

    def test_el_top1_contra_el_oro_se_reporta(self, corregido, record_property):
        renglones = por_orden("G01")
        reconocibles = ordenes("G01", "exacto") | ordenes("G01", "facil")
        kit = corregido["vista"]["kits"][0]

        aciertos = [
            linea["orden"]
            for linea in kit["lineas"]
            if linea["orden"] in reconocibles
            and linea.get("concepto") == renglones[linea["orden"]]["emparejamiento"]["concepto"]
        ]
        record_property("reconocibles", len(reconocibles))
        record_property("top1_aciertos", len(aciertos))
        record_property("top1_tasa", round(len(aciertos) / len(reconocibles), 4))
        assert reconocibles


@pytest.mark.nfr("NFR-PRE-03")
class TestNingunProductoFueraDelCatalogo:
    def test_ningun_sku_del_kit_ni_de_sus_alternativas_sale_de_fuera_del_catalogo(
        self, corregido, catalogo, record_property
    ):
        skus = [
            sku
            for _, linea in lineas(corregido["vista"])
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
        self, corregido, catalogo, record_property
    ):
        filas = asyncio.run(productos_de_los_kits(corregido["vista"]["trabajo_id"]))

        con_producto = [f for f in filas if f[1] is not None]
        fuera = sorted({f[1] for f in con_producto} - catalogo["ids"])
        record_property("lineas_guardadas", len(filas))
        record_property("producto_canonico_id_fuera", len(fuera))
        assert con_producto
        assert fuera == []
        assert {f[2] for f in con_producto} <= catalogo["skus"]


@pytest.mark.nfr("NFR-PRE-04")
class TestLoQueNoSeCompra:
    # H-A-42 (informativos): corregido en fix/hallazgos-qa; sale XPASS(strict) en la corrida del Mac y se quita el xfail.
    def test_los_informativos_salen_como_informativos(self, corregido, record_property):
        informativos = ordenes("G01", "informativo")
        kit = corregido["vista"]["kits"][0]

        obtenidos = {
            linea["orden"]: (linea["tipo"], linea["informativa"], linea.get("producto_elegido") is None)
            for linea in kit["lineas"]
            if linea["orden"] in informativos
        }
        esperados = {o: (por_orden("G01")[o]["parseo"]["tipo_item"], True, True) for o in informativos}
        record_property("informativos_comprables", sum(1 for o in obtenidos if not obtenidos[o][1]))
        assert obtenidos == esperados

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-42 y H-A-39: en la ruta rapida un hueco sale sin `mensaje` (o con producto, el "
            "compas sin chequeo de atributos) y nunca con una alternativa"
        ),
    )
    def test_los_huecos_dicen_no_tengo_y_ofrecen_una_alternativa(self, corregido, record_property):
        huecos = ordenes("G01", "hueco")
        kit = corregido["vista"]["kits"][0]

        malos = [
            linea["orden"]
            for linea in kit["lineas"]
            if linea["orden"] in huecos
            and (
                linea.get("producto_elegido") is not None
                or not (linea["mensaje"] or "").strip()
                or not linea["alternativas"]
            )
        ]
        record_property("huecos", len(huecos))
        record_property("huecos_sin_no_tengo", len(malos))
        assert malos == []


class TestLaCompra:
    def test_el_pago_aprobado_deja_la_orden_pagada_con_las_lineas_del_kit(
        self, http_flujo, corregido, record_property
    ):
        from tukit_comercio.pasarela import PasarelaFalsa

        padre, vista = corregido["padre"], corregido["vista"]
        perfil = vista["recomendado"]["perfil"]
        kit = next(k for k in vista["kits"] if k["perfil"] == perfil)
        # Lo mismo que `trabajos.ordenar` deja fuera: lo informativo, lo descartado, lo que no tiene
        # producto o precio y, desde f1e1a26, lo que quedo en cero. El diccionario de ingles «disponible
        # en casa» ya trae producto en C034 con cantidad 0 (N-170), y no se cobra (N-176).
        comprables = [
            {
                "sku": elegido["sku"],
                "nombre": elegido["nombre"],
                "cantidad": linea["unidades_a_comprar"],
                "precio_unitario": elegido["precio"],
            }
            for linea in kit["lineas"]
            if not linea["informativa"]
            and not linea.get("descartado")
            and (elegido := linea.get("producto_elegido"))
            and elegido["precio"]
            and int(linea["unidades_a_comprar"]) > 0
        ]

        orden = http_flujo.post(
            f"/v1/trabajos/{vista['trabajo_id']}/ordenar",
            headers=padre["cabecera"],
            json={"perfil": perfil, "correo": padre["correo"], "entrega": ENTREGA_FICTICIA},
        )
        assert orden.status_code == 201, orden.text
        datos = orden.json()
        assert datos["estado"] == "iniciado"
        assert datos["total"] == kit["total"] == sum(c["cantidad"] * c["precio_unitario"] for c in comprables)
        evento = PasarelaFalsa().emitir_evento(
            referencia=datos["referencia_wompi"],
            transaccion_id=datos["transaccion_wompi"],
            estado_wompi="APPROVED",
            # Desde fe8c030 el webhook trae el monto y comercio lo compara con el pedido.
            monto_centavos=datos["total"] * 100,
        )
        webhook = http_flujo.post("/v1/webhooks/wompi", json=evento)
        assert webhook.status_code == 200, webhook.text
        assert webhook.json()["pedido_transicionado"] is True
        # Desde 173ee80 la puerta no sirve `GET /v1/ordenes/{id}` (CONTRATO_API §9): el
        # acudiente lee su pedido en `mis-pedidos`, que comprueba que sea suyo (e82d03c).
        pagada = http_flujo.get(f"/v1/comercio/mis-pedidos/{datos['pedido_id']}", headers=padre["cabecera"])
        assert pagada.status_code == 200, pagada.text

        cuerpo = pagada.json()
        record_property("pedido_id", datos["pedido_id"])
        record_property("total", cuerpo["total"])
        record_property("lineas_pagadas", len(cuerpo["lineas"]))
        assert (cuerpo["estado"], cuerpo["trabajo_id"], cuerpo["total"]) == (
            "pagado",
            vista["trabajo_id"],
            kit["total"],
        )
        assert sorted(cuerpo["lineas"], key=_por_sku) == sorted(comprables, key=_por_sku)
