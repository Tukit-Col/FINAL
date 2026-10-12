"""Editar los kits ya publicados de una lista es publicar una version nueva.

El canonico vigente no se toca: `abrir_borrador` lo copia entero (items,
candidatos, resoluciones, kits y lineas) a un trabajo en `espera_revision`, el
admin lo corrige en la consola y `fijar_como_canonico` lo publica y mueve el
puntero. El canonico anterior queda publicado: el acudiente que ya empezo sigue
apuntando a el (`hijos[0].canonico_trabajo_id`) y ve los kits con que pago.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, update
from test_canonico_lista import GRADO, _preview, _puntero
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoTrabajo, PerfilKit


async def _canonico(motor, version: uuid.UUID | None = None) -> uuid.UUID:
    preview = await _preview(motor, version or uuid.uuid4())
    await trabajos.fijar_como_canonico(motor, preview)
    return preview


async def _lineas(motor, trabajo_id: uuid.UUID) -> list:
    async with motor.engine.begin() as conexion:
        return list(
            await conexion.execute(
                select(trabajos.LINEA, trabajos.KIT.c.perfil)
                .select_from(trabajos.LINEA.join(trabajos.KIT, trabajos.KIT.c.id == trabajos.LINEA.c.kit_id))
                .where(trabajos.KIT.c.trabajo_id == trabajo_id)
                .order_by(trabajos.KIT.c.perfil, trabajos.LINEA.c.orden)
            )
        )


async def _trabajo(motor, trabajo_id: uuid.UUID):
    async with motor.engine.begin() as conexion:
        return (
            await conexion.execute(select(trabajos.TRABAJO).where(trabajos.TRABAJO.c.id == trabajo_id))
        ).one()


class TestAbrirBorrador:
    async def test_copia_los_kits_en_un_trabajo_nuevo_en_revision(self, motor):
        canonico = await _canonico(motor)

        resultado = await trabajos.abrir_borrador(motor, canonico)

        borrador = uuid.UUID(resultado["trabajo_id"])
        assert borrador != canonico
        fila = await _trabajo(motor, borrador)
        assert fila.estado == EstadoTrabajo.ESPERA_REVISION.value
        assert fila.origen == trabajos.ORIGEN_CANONICO
        assert fila.hijos[0]["basado_en"] == str(canonico)
        originales, copiadas = await _lineas(motor, canonico), await _lineas(motor, borrador)
        assert len(copiadas) == len(originales) > 0
        assert [(fila.perfil, fila.descripcion, fila.sku) for fila in copiadas] == [
            (fila.perfil, fila.descripcion, fila.sku) for fila in originales
        ]
        # Ids nuevos: ni la linea ni su item crudo se comparten con el original.
        assert not {fila.id for fila in copiadas} & {fila.id for fila in originales}
        assert not {fila.item_crudo_id for fila in copiadas} & {fila.item_crudo_id for fila in originales}
        # El original sigue intacto y vigente.
        assert (await _trabajo(motor, canonico)).estado == EstadoTrabajo.PUBLICADO.value
        assert await _puntero(motor) == canonico

    async def test_un_segundo_pedido_devuelve_el_mismo_borrador(self, motor):
        canonico = await _canonico(motor)

        primero = await trabajos.abrir_borrador(motor, canonico)
        segundo = await trabajos.abrir_borrador(motor, canonico)

        assert primero["trabajo_id"] == segundo["trabajo_id"]

    async def test_editar_el_borrador_no_toca_el_canonico(self, motor):
        canonico = await _canonico(motor)
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])
        antes = [(fila.sku, fila.precio_unitario_cop) for fila in await _lineas(motor, canonico)]

        async with motor.engine.begin() as conexion:
            kits = select(trabajos.KIT.c.id).where(trabajos.KIT.c.trabajo_id == borrador)
            await conexion.execute(
                update(trabajos.LINEA)
                .where(trabajos.LINEA.c.kit_id.in_(kits))
                .values(sku=None, precio_unitario_cop=None, subtotal_cop=None)
            )

        assert [(fila.sku, fila.precio_unitario_cop) for fila in await _lineas(motor, canonico)] == antes

    async def test_solo_se_edita_el_canonico_vigente(self, motor):
        viejo = await _canonico(motor)
        await _canonico(motor)

        with pytest.raises(trabajos.BorradorDesactualizado):
            await trabajos.abrir_borrador(motor, viejo)

    async def test_grados_canonicos_avisa_el_borrador_abierto(self, motor):
        canonico = await _canonico(motor)
        (grado,) = await trabajos.grados_canonicos(motor, colegio_id=COLEGIO)
        assert grado["borrador_trabajo_id"] is None
        assert grado["publicado_en"]

        borrador = await trabajos.abrir_borrador(motor, canonico)

        (grado,) = await trabajos.grados_canonicos(motor, colegio_id=COLEGIO)
        assert grado["borrador_trabajo_id"] == borrador["trabajo_id"]

    async def test_la_cola_lo_marca_como_edicion(self, motor):
        canonico = await _canonico(motor)
        borrador = await trabajos.abrir_borrador(motor, canonico)

        cola = await trabajos.cola(motor)

        fila = next(t for t in cola["trabajos"] if t["trabajo_id"] == borrador["trabajo_id"])
        assert fila["edicion_de"] == str(canonico)


class TestPublicarBorrador:
    async def test_mueve_el_puntero_y_conserva_la_version_anterior(self, motor):
        canonico = await _canonico(motor)
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])

        await trabajos.fijar_como_canonico(motor, borrador)

        assert await _puntero(motor) == borrador
        assert (await _trabajo(motor, canonico)).estado == EstadoTrabajo.PUBLICADO.value
        (grado,) = await trabajos.grados_canonicos(motor, colegio_id=COLEGIO)
        assert grado["borrador_trabajo_id"] is None

    async def test_recalcula_la_disponibilidad_de_cada_kit(self, motor):
        canonico = await _canonico(motor)
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])
        async with motor.engine.begin() as conexion:
            kits = select(trabajos.KIT.c.id).where(trabajos.KIT.c.trabajo_id == borrador)
            primera = await conexion.scalar(
                select(trabajos.LINEA.c.id)
                .where(trabajos.LINEA.c.kit_id.in_(kits), trabajos.LINEA.c.informativa.is_(False))
                .limit(1)
            )
            await conexion.execute(
                update(trabajos.LINEA)
                .where(trabajos.LINEA.c.id == primera)
                .values(precio_unitario_cop=None, subtotal_cop=None)
            )

        await trabajos.fijar_como_canonico(motor, borrador)

        async with motor.engine.begin() as conexion:
            objetivos = [
                k.objetivos
                for k in await conexion.execute(
                    select(trabajos.KIT.c.objetivos).where(trabajos.KIT.c.trabajo_id == borrador)
                )
            ]
        assert any(o["disponibilidad"] < 1 for o in objetivos)

    async def test_el_acudiente_que_ya_empezo_sigue_con_la_version_anterior(self, motor):
        canonico = await _canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado=GRADO,
            anio_lectivo=2026,
            perfil=PerfilKit.AHORRADOR.value,
            usuario_id=uuid.uuid4(),
            catalogo=_catalogo_verificado(),
        )
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])
        await trabajos.fijar_como_canonico(motor, borrador)

        fila = await _trabajo(motor, uuid.UUID(aplicado["trabajo_id"]))
        assert fila.hijos[0]["canonico_trabajo_id"] == str(canonico)

    async def test_un_borrador_de_una_version_reemplazada_no_se_publica(self, motor):
        canonico = await _canonico(motor)
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])
        # Mientras tanto la lista se reaprobo y hay otro canonico vigente.
        nuevo = await _canonico(motor)

        with pytest.raises(trabajos.BorradorDesactualizado):
            await trabajos.fijar_como_canonico(motor, borrador)
        assert await _puntero(motor) == nuevo


async def _linea_con_producto(motor, trabajo_id: uuid.UUID):
    return next(fila for fila in await _lineas(motor, trabajo_id) if fila.sku and not fila.informativa)


class TestKitsPublicadosNoSeEditanEnSitio:
    async def test_cambiar_el_producto_de_un_canonico_publicado_se_niega(self, motor):
        canonico = await _canonico(motor)
        linea = await _linea_con_producto(motor, canonico)

        with pytest.raises(trabajos.KitsPublicadosNoEditables):
            await trabajos.fijar_producto_en_linea(
                motor,
                canonico,
                linea.perfil,
                linea.item_crudo_id,
                linea.sku,
                catalogo=_catalogo_verificado(),
            )

    async def test_marcar_sin_coincidencia_en_un_canonico_publicado_se_niega(self, motor):
        canonico = await _canonico(motor)
        linea = await _linea_con_producto(motor, canonico)

        with pytest.raises(trabajos.KitsPublicadosNoEditables):
            await trabajos.decidir_linea(motor, canonico, linea.item_crudo_id, estado="HUECO_CATALOGO")
        assert (await _linea_con_producto(motor, canonico)).sku == linea.sku

    async def test_en_el_borrador_si_se_edita(self, motor):
        canonico = await _canonico(motor)
        borrador = uuid.UUID((await trabajos.abrir_borrador(motor, canonico))["trabajo_id"])
        linea = await _linea_con_producto(motor, borrador)

        await trabajos.decidir_linea(motor, borrador, linea.item_crudo_id, estado="HUECO_CATALOGO")

        quedan = {fila.item_crudo_id: fila.sku for fila in await _lineas(motor, borrador)}
        assert quedan[linea.item_crudo_id] is None
