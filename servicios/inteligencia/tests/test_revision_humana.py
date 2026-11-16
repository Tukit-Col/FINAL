"""La revision humana de un trabajo: la cola, validar lineas, aprobar y borrar.

Un trabajo de colegio sale de la optimizacion en `espera_revision` y nadie lo
ve hasta que una persona lo aprueba (AD-03 a AD-06). Aprobar publica y deja el
evento en la bandeja en la misma transaccion; la lista aprobada fija el puntero
al kit canonico del grado. Validar una linea deja quien y cuando.
"""

from __future__ import annotations

import uuid

import pytest
from _ayudas_inteligencia import COLEGIO, catalogo_simple, crear_y_procesar, sembrar_canonico
from conftest import CatalogoFalso, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo


class TestLaRevisionHumana:
    async def test_aprobar_publica_y_deja_el_evento_en_la_bandeja(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await crear_y_procesar(motor)
        actor = uuid.uuid4()
        resultado = await trabajos.revisar(motor, trabajo_id, decision="aprobar", nota="ok", actor=actor)

        vista = await trabajos.ver(motor, trabajo_id)
        assert resultado["estado"] == EstadoTrabajo.PUBLICADO.value
        assert vista["estado"] == EstadoTrabajo.PUBLICADO.value
        assert len(vista["kits"]) == 2
        assert vista["recomendado"]["perfil"] == "Ahorrador"

        async with motor.engine.begin() as conexion:
            eventos = list(await conexion.execute(select(trabajos.BANDEJA)))
        assert [e.tipo for e in eventos] == ["kits_publicados"]

    async def test_publicar_dos_veces_no_se_puede(self, motor):
        """No es idempotente: es un segundo aviso al acudiente."""
        trabajo_id, _ = await crear_y_procesar(motor)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        with pytest.raises(trabajos.TransicionIlegal):
            await trabajos.revisar(motor, trabajo_id, decision="aprobar")

    async def test_un_preview_de_onboarding_no_se_publica(self, motor):
        """Un preview no tiene acudiente: publicarlo dejaria un `kits_publicados`
        sin destinatario que el repartidor reintentaria sin fin. Se rechaza."""
        from sqlalchemy import func, select

        respuesta = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            origen="preview_onboarding",
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_simple())

        with pytest.raises(trabajos.PreviewNoPublicable):
            await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        # No se emitio ningun evento sin destinatario.
        async with motor.engine.begin() as conexion:
            eventos = await conexion.scalar(select(func.count()).select_from(trabajos.BANDEJA))
        assert eventos == 0

    async def test_borrar_un_trabajo_en_revision_lo_saca_de_la_cola(self, motor):
        from sqlalchemy import func, select

        trabajo_id, _ = await crear_y_procesar(motor)
        assert (await trabajos.cola(motor))["total"] == 1

        await trabajos.eliminar(motor, trabajo_id)

        assert (await trabajos.cola(motor))["total"] == 0
        # La cascada se llevo etapas, items y kits: no quedan huerfanos.
        async with motor.engine.begin() as conexion:
            for tabla in (trabajos.ETAPA, trabajos.ITEM, trabajos.KIT):
                sobran = await conexion.scalar(
                    select(func.count()).select_from(tabla).where(tabla.c.trabajo_id == trabajo_id)
                )
                assert sobran == 0

    async def test_borrar_un_publicado_esta_prohibido(self, motor):
        trabajo_id, _ = await crear_y_procesar(motor)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        with pytest.raises(trabajos.TrabajoProtegido):
            await trabajos.eliminar(motor, trabajo_id)

        # Sigue vivo y publicado.
        assert (await trabajos.ver(motor, trabajo_id))["estado"] == EstadoTrabajo.PUBLICADO.value

    async def test_borrar_uno_que_no_existe_es_TrabajoNoExiste(self, motor):
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.eliminar(motor, uuid.uuid4())

    async def test_la_lista_aprobada_deja_el_puntero_canonico_del_grado(self, motor):
        from sqlalchemy import select

        canonico = await sembrar_canonico(motor)

        async with motor.engine.begin() as conexion:
            puntero = list(await conexion.execute(select(trabajos.KIT_CANONICO)))
        assert len(puntero) == 1
        assert puntero[0].colegio_id == COLEGIO
        assert puntero[0].grado == "Cuarto"
        assert puntero[0].trabajo_id == canonico

    async def test_aprobar_el_trabajo_de_un_acudiente_no_toca_el_canonico(self, motor):
        """El canonico sale de la lista aprobada. El kit de un papa lleva sus
        preferencias (presupuesto, prioridad, personaje) y es solo suyo: antes,
        aprobarlo en la cola de revision lo volvia el canonico de su grado y los
        papas siguientes recibian un kit armado con las preferencias de otro."""
        from sqlalchemy import select

        canonico = await sembrar_canonico(motor)
        del_papa, _ = await crear_y_procesar(motor)
        await trabajos.revisar(motor, del_papa, decision="aprobar")

        assert (await trabajos.ver(motor, del_papa))["estado"] == EstadoTrabajo.PUBLICADO.value
        async with motor.engine.begin() as conexion:
            puntero = list(await conexion.execute(select(trabajos.KIT_CANONICO)))
        assert [p.trabajo_id for p in puntero] == [canonico]

    async def test_sin_canonico_aprobar_al_acudiente_no_crea_uno(self, motor):
        from sqlalchemy import func, select

        del_papa, _ = await crear_y_procesar(motor)
        await trabajos.revisar(motor, del_papa, decision="aprobar")

        async with motor.engine.begin() as conexion:
            punteros = await conexion.scalar(select(func.count()).select_from(trabajos.KIT_CANONICO))
        assert punteros == 0

    async def test_una_lista_reaprobada_reemplaza_el_puntero(self, motor):
        from sqlalchemy import select

        await sembrar_canonico(motor)
        segundo = await sembrar_canonico(motor)

        async with motor.engine.begin() as conexion:
            puntero = list(await conexion.execute(select(trabajos.KIT_CANONICO)))
        # Una sola cache bendita por grado: la lista nueva desbanca a la vieja.
        assert len(puntero) == 1
        assert puntero[0].trabajo_id == segundo

    async def test_aprobar_un_kit_sin_lineas_comprables_se_niega_y_no_fija_canonico(self, motor):
        # Todos los renglones son licencia digital (informativos, sin precio): el
        # kit no tiene NADA que Tukit pueda cobrar. Aprobarlo como canonico solo
        # garantizaria el 404 "sin lineas comprables" en el checkout, asi que se
        # niega con `CheckoutRechazado` y NO se fija el puntero ni se emite aviso.
        from sqlalchemy import func, select

        catalogo = CatalogoFalso(
            renglones=[
                renglon(
                    1,
                    "Plan lector virtual RAZ-PLUS",
                    tipo_item="licencia_digital",
                    modo_adquisicion="plataforma",
                    instruccion_colegio="Se adquiere con QUOVIX.",
                ),
            ],
            respuestas={},  # sin emparejamiento: el renglon no gana producto ni precio
        )
        trabajo_id, _ = await crear_y_procesar(motor, catalogo=catalogo)

        with pytest.raises(trabajos.CheckoutRechazado) as exc:
            await trabajos.revisar(motor, trabajo_id, decision="aprobar")
        assert exc.value.estado == 409
        assert exc.value.cuerpo["error"] == "kit_sin_lineas"

        # El rollback dejo el trabajo en espera de revision, sin canonico ni evento.
        assert (await trabajos.ver(motor, trabajo_id))["estado"] == EstadoTrabajo.ESPERA_REVISION.value
        async with motor.engine.begin() as conexion:
            punteros = await conexion.scalar(select(func.count()).select_from(trabajos.KIT_CANONICO))
            eventos = await conexion.scalar(select(func.count()).select_from(trabajos.BANDEJA))
        assert punteros == 0
        assert eventos == 0


class TestLaColaDeRevision:
    async def test_la_cola_lista_lo_que_espera_a_una_persona(self, motor):
        await crear_y_procesar(motor)
        cola = await trabajos.cola(motor)

        assert cola["total"] == 1
        # El punzon quedo sin match y la licencia no pasa por el catalogo.
        assert cola["trabajos"][0]["lineas_a_revisar"] == 1

    async def test_la_cola_dice_de_que_colegio_y_grado_es(self, motor):
        """Sin esto la consola mostraba "Sin identificar" en trabajos que si lo
        sabian: el colegio y el grado viajan en los hijos del trabajo."""
        await crear_y_procesar(motor)
        entrada = (await trabajos.cola(motor))["trabajos"][0]

        assert entrada["colegios"] and entrada["grados"]
        assert entrada["origen"]


class TestValidarUnaLinea:
    async def test_validar_sin_sku_una_linea_ambigua_toma_el_producto_de_los_kits(self, motor):
        """El "Confirmar las elegidas" llega sin sku. En una linea AMBIGUA la
        resolucion no tiene candidato (eligio el optimizador, kit por kit), y
        validarla asi la dejaba resuelta y sin producto: 500 por el CHECK."""
        from sqlalchemy import select, update

        trabajo_id, _ = await crear_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(trabajos.LINEA.c.item_crudo_id, trabajos.CANDIDATO.c.id)
                    .select_from(
                        trabajos.LINEA.join(trabajos.KIT, trabajos.KIT.c.id == trabajos.LINEA.c.kit_id).join(
                            trabajos.CANDIDATO,
                            (trabajos.CANDIDATO.c.item_crudo_id == trabajos.LINEA.c.item_crudo_id)
                            & (trabajos.CANDIDATO.c.sku == trabajos.LINEA.c.sku),
                        )
                    )
                    .where(trabajos.KIT.c.trabajo_id == trabajo_id)
                    .limit(1)
                )
            ).first()
            assert fila is not None, "el trabajo de prueba debe tener una linea con candidato"
            item, candidato = fila
            await conexion.execute(
                update(trabajos.RESOLUCION)
                .where(trabajos.RESOLUCION.c.item_crudo_id == item)
                .values(estado=EstadoResolucion.AMBIGUO.value, candidato_item_id=None)
            )

        await trabajos.decidir_linea(motor, trabajo_id, item, estado=EstadoResolucion.RESUELTO_AUTO.value)

        async with motor.engine.begin() as conexion:
            resolucion = (
                await conexion.execute(
                    select(trabajos.RESOLUCION).where(trabajos.RESOLUCION.c.item_crudo_id == item)
                )
            ).one()
        assert resolucion.estado == EstadoResolucion.RESUELTO_AUTO.value
        assert resolucion.candidato_item_id == candidato

    async def test_validar_una_linea_sin_ningun_producto_es_un_error_con_causa(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await crear_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            # El punzon (orden 4) quedo sin match: no hay candidato ni producto en los kits.
            item = (
                await conexion.execute(
                    select(trabajos.ITEM.c.id).where(
                        trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == 4
                    )
                )
            ).scalar_one()

        with pytest.raises(trabajos.SinProductoQueValidar):
            await trabajos.decidir_linea(motor, trabajo_id, item, estado=EstadoResolucion.RESUELTO_AUTO.value)

    async def test_validar_una_linea_deja_quien_y_cuando(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await crear_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            item = (
                await conexion.execute(
                    select(trabajos.ITEM.c.id).where(
                        trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == 4
                    )
                )
            ).scalar_one()

        actor = uuid.uuid4()
        await trabajos.decidir_linea(
            motor,
            trabajo_id,
            item,
            estado=EstadoResolucion.HUECO_CATALOGO.value,
            actor=actor,
            motivo="lo miramos y no lo tenemos",
        )

        async with motor.engine.begin() as conexion:
            resolucion = (
                await conexion.execute(
                    select(trabajos.RESOLUCION).where(trabajos.RESOLUCION.c.item_crudo_id == item)
                )
            ).one()
            transiciones = list(
                await conexion.execute(
                    select(trabajos.TRANSICION).where(
                        trabajos.TRANSICION.c.resolucion_item_id == resolucion.id
                    )
                )
            )

        assert resolucion.estado == EstadoResolucion.HUECO_CATALOGO.value
        assert resolucion.decidido_por == actor
        assert [t.estado_nuevo for t in transiciones] == [
            EstadoResolucion.SIN_MATCH.value,
            EstadoResolucion.HUECO_CATALOGO.value,
        ]
        assert transiciones[-1].decidida_por == actor
