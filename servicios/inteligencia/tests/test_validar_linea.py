"""Validar una linea y marcarla sin coincidencia, sin 500 y sin cobrar huecos.

Arreglos rescatados de la rama preview-kits (su cola y su vista previa no):

- Validar una linea AMBIGUO daba 500. La ruta lenta deja `candidato_item_id`
  nulo en todo lo que no es RESUELTO_AUTO; validar sin `sku` escribia
  RESUELTO_AUTO sin candidato y el CHECK `resolucion_resuelta_tiene_candidato`
  reventaba. Ahora se valida el producto que la linea tiene en el kit
  (registrandolo como candidato si no lo era) y, sin producto, se responde 422
  con `campo`.
- Un `sku` que no era candidato validaba OTRO producto en silencio.
- "Sin coincidencia" dejaba el producto y el precio en las lineas: `ordenar` lo
  cobraba aunque el acudiente lo viera como hueco.
- La nota de validar (`nota` en el contrato TS) se perdia.

Todo corre sobre el SQLite en memoria y un catalogo en memoria (sin red).
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from _ayudas_inteligencia import COLEGIO, CatalogoPreview
from conftest import opcion, reconocido, renglon
from sqlalchemy import select
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo

CUADERNO = "2 cuadernos cuadriculados"
CARTUCHERA = "1 cartuchera"


def _catalogo(version_id: str, *, ambiguo: bool = True, precios: bool = True) -> CatalogoPreview:
    """Una version sin revisar: el cuaderno se resuelve solo y la cartuchera
    queda AMBIGUO (parecido 0.5 < tau), que es el caso del 500."""
    precio = (lambda p: p) if precios else (lambda _p: None)
    return CatalogoPreview(
        version_vigente=version_id,
        grado="Cuarto",
        renglones=[renglon(1, CUADERNO, cantidad=2), renglon(2, CARTUCHERA)],
        respuestas={
            CUADERNO: reconocido(
                CUADERNO,
                "C001",
                [
                    opcion("TK-C001-ECO", "economico", precio(4500)),
                    opcion("TK-C001-CON", "confiable", precio(6000)),
                ],
            ),
            CARTUCHERA: reconocido(
                CARTUCHERA,
                "C009",
                [
                    opcion("TK-C009-ECO", "economico", precio(8000)),
                    opcion("TK-C009-CON", "confiable", precio(15000)),
                ],
                parecido=0.5 if ambiguo else 0.95,
            ),
        },
    )


async def _preview(motor, catalogo: CatalogoPreview, version_id: str) -> uuid.UUID:
    """Arma el preview igual que `POST /v1/admin/onboarding/{id}/preview`."""
    respuesta = await trabajos.crear(
        motor,
        hijos=[
            {
                "referencia": "preview",
                "colegio_id": COLEGIO,
                "grado": "Cuarto",
                "anio_lectivo": 2026,
                "version_id": version_id,
            }
        ],
        preferencias={},
        origen="preview_onboarding",
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    assert (
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo) == EstadoTrabajo.ESPERA_REVISION.value
    )
    return trabajo_id


async def _item(motor, trabajo_id: uuid.UUID, orden: int) -> uuid.UUID:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(
            select(trabajos.ITEM.c.id).where(
                trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == orden
            )
        )


async def _sku_recomendado(motor, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> str:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(
            select(trabajos.LINEA.c.sku)
            .select_from(trabajos.LINEA.join(trabajos.KIT, trabajos.KIT.c.id == trabajos.LINEA.c.kit_id))
            .where(
                trabajos.KIT.c.trabajo_id == trabajo_id,
                trabajos.KIT.c.recomendado.is_(True),
                trabajos.LINEA.c.item_crudo_id == item_id,
            )
        )


async def _resolucion(motor, item_id: uuid.UUID):
    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(trabajos.RESOLUCION).where(trabajos.RESOLUCION.c.item_crudo_id == item_id)
            )
        ).one()
        sku = None
        if fila.candidato_item_id is not None:
            sku = await conexion.scalar(
                select(trabajos.CANDIDATO.c.sku).where(trabajos.CANDIDATO.c.id == fila.candidato_item_id)
            )
        estados_linea = {
            f.estado_resolucion
            for f in await conexion.execute(
                select(trabajos.LINEA.c.estado_resolucion).where(trabajos.LINEA.c.item_crudo_id == item_id)
            )
        }
    return fila, sku, estados_linea


@pytest.fixture()
def version_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        yield http


# ---------------------------------------------------------------------------
# Validar sin 500
# ---------------------------------------------------------------------------


class TestValidarLinea:
    async def test_validar_ambiguo_sin_candidato_resuelve_con_el_producto_del_kit(self, motor, version_id):
        catalogo = _catalogo(version_id)
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)
        antes, _, _ = await _resolucion(motor, item_id)
        assert antes.estado == EstadoResolucion.AMBIGUO.value
        assert antes.candidato_item_id is None  # el origen del 500
        esperado = await _sku_recomendado(motor, trabajo_id, item_id)

        respuesta = await trabajos.decidir_linea(
            motor, trabajo_id, item_id, estado=EstadoResolucion.RESUELTO_AUTO.value, catalogo=catalogo
        )

        fila, sku, estados_linea = await _resolucion(motor, item_id)
        assert respuesta["sku"] == esperado
        assert fila.estado == EstadoResolucion.RESUELTO_AUTO.value
        assert sku == esperado
        assert fila.decidido_en is not None
        # Los kits dejan de mostrar la linea como pendiente.
        assert estados_linea == {EstadoResolucion.RESUELTO_AUTO.value}
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True, incluir_admin=True)
        assert str(item_id) not in vista["lineas_pendientes"]

    async def test_un_sku_que_no_era_candidato_se_registra_y_se_valida(self, motor, version_id):
        # El personaje del Fan o un producto fijado por kit no son candidatos del
        # item; validarlos es legitimo y no debe tropezar con el CHECK.
        catalogo = _catalogo(version_id)
        catalogo.respuestas["otro"] = reconocido("otro", "C099", [opcion("TK-FAN-1", "confiable", 9900)])
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        await trabajos.decidir_linea(
            motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.RESUELTO_AUTO.value,
            sku="TK-FAN-1",
            catalogo=catalogo,
        )

        fila, sku, _ = await _resolucion(motor, item_id)
        assert fila.estado == EstadoResolucion.RESUELTO_AUTO.value
        assert sku == "TK-FAN-1"

    async def test_sin_producto_rechaza_con_motivo(self, motor, version_id):
        catalogo = _catalogo(version_id)
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        with pytest.raises(trabajos.SinProductoQueValidar):
            await trabajos.decidir_linea(
                motor,
                trabajo_id,
                item_id,
                estado=EstadoResolucion.RESUELTO_AUTO.value,
                sku="NO-EXISTE",
                catalogo=catalogo,
            )
        fila, _, _ = await _resolucion(motor, item_id)
        assert fila.estado == EstadoResolucion.AMBIGUO.value  # nada se escribio

    async def test_marcar_sin_coincidencia_tambien_actualiza_las_lineas(self, motor, version_id):
        catalogo = _catalogo(version_id)
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        await trabajos.decidir_linea(
            motor, trabajo_id, item_id, estado=EstadoResolucion.HUECO_CATALOGO.value, motivo="no lo tenemos"
        )

        fila, _, estados_linea = await _resolucion(motor, item_id)
        assert fila.candidato_item_id is None
        assert estados_linea == {EstadoResolucion.HUECO_CATALOGO.value}

    async def test_sin_coincidencia_quita_el_producto_y_baja_el_total(self, motor, version_id):
        # "No lo tenemos" no se puede cobrar: `ordenar` cobra toda linea con sku
        # y precio, asi que la linea tiene que quedar vacia en todos los kits.
        catalogo = _catalogo(version_id)
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)
        antes = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        subtotales = {
            k["perfil"]: next(
                linea["subtotal_linea"] or 0 for linea in k["lineas"] if linea["item_id"] == str(item_id)
            )
            for k in antes["kits"]
        }
        assert any(subtotales.values())

        await trabajos.decidir_linea(
            motor, trabajo_id, item_id, estado=EstadoResolucion.HUECO_CATALOGO.value, motivo="no lo tenemos"
        )

        async with motor.engine.begin() as conexion:
            lineas = list(
                await conexion.execute(
                    select(trabajos.LINEA).where(trabajos.LINEA.c.item_crudo_id == item_id)
                )
            )
        # Sin personaje ni `equilibrio`, el preview trae Ahorrador y Premium (ADR 0030).
        assert len(lineas) == len(antes["kits"]) == 2
        assert all(
            linea.sku is None and linea.precio_unitario_cop is None and linea.subtotal_cop is None
            for linea in lineas
        )
        despues = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        for kit in despues["kits"]:
            total_antes = next(k["total"] for k in antes["kits"] if k["perfil"] == kit["perfil"])
            assert kit["total"] == total_antes - subtotales[kit["perfil"]]


class TestValidarPorApi:
    async def test_validar_sin_cuerpo_no_da_500(self, motor, cliente, version_id):
        catalogo = _catalogo(version_id)
        app.state.catalogo = catalogo
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        respuesta = await cliente.post(f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json={})

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["estado"] == EstadoResolucion.RESUELTO_AUTO.value

    async def test_lote_valida_el_elegido_que_manda_la_consola(self, motor, cliente, version_id):
        # "Confirmar las N elegidas" manda el sku que cada linea muestra.
        catalogo = _catalogo(version_id)
        app.state.catalogo = catalogo
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)
        elegido = await _sku_recomendado(motor, trabajo_id, item_id)

        respuesta = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json={"sku": elegido}
        )

        assert respuesta.status_code == 200, respuesta.text
        _, sku, _ = await _resolucion(motor, item_id)
        assert sku == elegido

    async def test_la_nota_de_validar_queda_en_la_transicion(self, motor, cliente, version_id):
        # El contrato TS manda `nota`; antes el backend solo leia `motivo` y la
        # nota del revisor se perdia sin error.
        catalogo = _catalogo(version_id)
        app.state.catalogo = catalogo
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        respuesta = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json={"nota": "revisado en tienda"}
        )

        assert respuesta.status_code == 200, respuesta.text
        fila, _, _ = await _resolucion(motor, item_id)
        async with motor.engine.begin() as conexion:
            motivos = list(
                await conexion.scalars(
                    select(trabajos.TRANSICION.c.motivo).where(
                        trabajos.TRANSICION.c.resolucion_item_id == fila.id
                    )
                )
            )
        assert "revisado en tienda" in motivos

    async def test_sin_producto_es_422_con_campo(self, motor, cliente, version_id):
        catalogo = _catalogo(version_id)
        app.state.catalogo = catalogo
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        respuesta = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json={"sku": "NO-EXISTE"}
        )

        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "sin_producto_que_validar"
        assert cuerpo["campo"] == "sku"
        assert cuerpo["mensaje"]

    async def test_linea_sin_producto_en_el_kit_es_422(self, motor, cliente, version_id):
        # Sin precios no hay producto en la LINEA y la resolucion no apunta a
        # nada: validar "el elegido" no tiene que confirmar.
        catalogo = _catalogo(version_id)
        catalogo.respuestas[CARTUCHERA]["opciones"] = []
        catalogo.respuestas[CARTUCHERA]["estado"] = "sin_match"
        app.state.catalogo = catalogo
        trabajo_id = await _preview(motor, catalogo, version_id)
        item_id = await _item(motor, trabajo_id, 2)

        respuesta = await cliente.post(f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json={})

        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "sku"
