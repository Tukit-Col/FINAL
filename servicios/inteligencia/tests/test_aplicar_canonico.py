"""La ruta rapida del acudiente: aplicar el kit canonico, cambiarlo y ordenarlo.

`aplicar_canonico` no re-optimiza ni copia kits: crea el trabajo del acudiente
apuntando al canonico del grado y congela su pedido. Los cambios del acudiente
viven en SU trabajo (`cambios`), nunca en las lineas del canonico, que son las
que reciben los demas. Ordenar arma la orden hacia Comercio sin ids de base, y
solo el dueno puede ordenar.
"""

from __future__ import annotations

import uuid

import pytest
from _ayudas_inteligencia import (
    COLEGIO,
    catalogo_simple,
    crear_y_procesar,
    linea_del_kit,
    sembrar_canonico,
    total_del_kit,
)
from conftest import opcion
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoTrabajo


class TestAplicarCanonico:
    """La ruta rapida del acudiente: sin re-optimizar, sin cola, un pedido."""

    async def test_aplicar_no_copia_kits_y_congela_el_pedido(self, motor):
        from sqlalchemy import func, select

        canonico = await sembrar_canonico(motor)

        async with motor.engine.begin() as conexion:
            kits_antes = await conexion.scalar(select(func.count()).select_from(trabajos.KIT))

        usuario = uuid.uuid4()
        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=usuario,
            catalogo=catalogo_simple(),
        )
        parent_id = uuid.UUID(resultado["trabajo_id"])

        async with motor.engine.begin() as conexion:
            # Modelo por REFERENCIA: no nacieron kits nuevos.
            assert await conexion.scalar(select(func.count()).select_from(trabajos.KIT)) == kits_antes
            # El trabajo del acudiente es parent_apply, publicado, sin etapas.
            fila = (
                await conexion.execute(select(trabajos.TRABAJO).where(trabajos.TRABAJO.c.id == parent_id))
            ).one()
            assert fila.origen == "parent_apply"
            assert fila.estado == EstadoTrabajo.PUBLICADO.value
            assert fila.hijos[0]["canonico_trabajo_id"] == str(canonico)
            # El pedido congelado quedo en la bandeja para Comercio.
            pedidos = [
                e for e in await conexion.execute(select(trabajos.BANDEJA)) if e.tipo == "pedido_solicitado"
            ]
        assert len(pedidos) == 1
        assert pedidos[0].carga["total_cop"] == resultado["total"]
        assert resultado["total"] > 0

    async def test_el_personaje_se_congela_en_las_anclas(self, motor):
        from sqlalchemy import select

        # Catalogo con un personaje en el ancla C001, ademas del neutral.
        catalogo = catalogo_simple()
        catalogo.respuestas["2 cuadernos cuadriculados"]["opciones"].append(
            opcion("TK-C001-FAN", "confiable", 9000, personaje="cars")
        )
        await sembrar_canonico(motor, catalogo=catalogo)

        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Fan",
            personaje="cars",
            catalogo=catalogo,
        )
        parent_id = uuid.UUID(resultado["trabajo_id"])

        async with motor.engine.begin() as conexion:
            pedido = next(
                e
                for e in await conexion.execute(select(trabajos.BANDEJA))
                if e.tipo == "pedido_solicitado" and e.agregado_id == parent_id
            )
        c001 = next(linea for linea in pedido.carga["lineas"] if linea.get("concepto") == "C001")
        assert c001["producto_elegido"]["personaje"] == "cars"
        assert c001["producto_elegido"]["sku"] == "TK-C001-FAN"

    async def test_sin_cache_es_TrabajoNoExiste(self, motor):
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.aplicar_canonico(
                motor,
                colegio_id=COLEGIO,
                grado="Cuarto",
                anio_lectivo=2026,
                perfil="Ahorrador",
                catalogo=catalogo_simple(),
            )

    async def test_ver_sigue_el_puntero_y_pinta_el_kit_con_personaje(self, motor):
        # ver() de un parent_apply no tiene kits propios: sigue el puntero al
        # canonico y arma el unico kit del perfil, con el personaje en el ancla.
        catalogo = catalogo_simple()
        catalogo.respuestas["2 cuadernos cuadriculados"]["opciones"].append(
            opcion("TK-C001-FAN", "confiable", 9000, personaje="cars")
        )
        await sembrar_canonico(motor, catalogo=catalogo)

        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Fan",
            personaje="cars",
            catalogo=catalogo,
        )
        parent_id = uuid.UUID(resultado["trabajo_id"])

        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        # Ahorrador y Premium del canonico, mas el Fan armado para este
        # acudiente (el Ahorrador con el personaje); el elegido va marcado.
        assert [k["perfil"] for k in vista["kits"]] == ["Ahorrador", "Fan", "Premium"]
        assert vista["recomendado"]["perfil"] == "Fan"
        ahorrador = next(k for k in vista["kits"] if k["perfil"] == "Ahorrador")
        c001_ahorrador = next(linea for linea in ahorrador["lineas"] if linea.get("concepto") == "C001")
        assert c001_ahorrador["producto_elegido"]["sku"] == "TK-C001-ECO"  # el personaje solo va en el Fan
        elegido = next(k for k in vista["kits"] if k["perfil"] == "Fan")
        assert elegido["total"] == resultado["total"]
        c001 = next(linea for linea in elegido["lineas"] if linea.get("concepto") == "C001")
        assert c001["producto_elegido"]["sku"] == "TK-C001-FAN"
        # Las lineas del kit aplicado son del canonico: el personaje pedido se
        # nombra con esa misma clave, para que la web y el asistente lo casen.
        assert vista["personajes_por_hijo"] == {"canonico": ["cars"]}
        assert elegido["personaje_sin_encaje"] == []
        # Los objetivos se calculan sobre las lineas aplicadas. Antes iban vacios
        # y la web pintaba "NaN% con precio confirmado".
        objetivos = elegido["objetivos"]
        assert objetivos["costo"] == resultado["total"]
        assert 0.0 <= objetivos["disponibilidad"] <= 1.0
        assert 0.0 <= objetivos["fidelidad"] <= 1.0

    async def test_ordenar_arma_la_orden_server_to_server_sin_ids_de_base(self, motor):
        # El checkout: del kit publicado a la orden. Se verifica que Inteligencia
        # manda a Comercio SOLO sku+precio (nunca un id canonico: RPO cero) y que
        # devuelve la url de la pasarela para mandar al acudiente a pagar.
        await sembrar_canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=(acudiente := uuid.uuid4()),
            catalogo=catalogo_simple(),
        )
        parent_id = uuid.UUID(aplicado["trabajo_id"])

        class ComercioFalso:
            def __init__(self):
                self.orden_enviada = None

            async def crear_orden(self, cuerpo):
                self.orden_enviada = cuerpo
                return 201, {"pedido_id": "ped-1", "total": cuerpo_total(cuerpo)}

            async def iniciar_pago(self, pedido_id, cuerpo):
                return 201, {"pago_id": "pago-1", "url_redireccion": "https://pasarela/xy"}

        def cuerpo_total(c):
            return sum(linea["precio_unitario"] * linea["cantidad"] for linea in c["lineas"])

        comercio = ComercioFalso()
        resultado = await trabajos.ordenar(
            motor,
            parent_id,
            portador=acudiente,
            perfil="Ahorrador",
            entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
            correo="ana@example.com",
            comercio=comercio,
            catalogo=catalogo_simple(),
        )
        assert resultado["url_redireccion"] == "https://pasarela/xy"
        assert resultado["pedido_id"] == "ped-1"
        # RPO cero: ni una linea lleva id canonico, solo sku.
        assert comercio.orden_enviada["lineas"]
        lineas_enviadas = comercio.orden_enviada["lineas"]
        assert all("producto_canonico_id" not in linea for linea in lineas_enviadas)
        assert all(linea["sku"] and linea["precio_unitario"] > 0 for linea in lineas_enviadas)
        assert comercio.orden_enviada["trabajo_id"] == str(parent_id)

    async def test_ordenar_reenvia_el_rechazo_de_negocio_de_comercio(self, motor):
        await sembrar_canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=(acudiente := uuid.uuid4()),
            catalogo=catalogo_simple(),
        )
        parent_id = uuid.UUID(aplicado["trabajo_id"])

        class ComercioRechaza:
            async def crear_orden(self, cuerpo):
                return 422, {"error": "precio_cambiado", "mensaje": "cambio"}

            async def iniciar_pago(self, pedido_id, cuerpo):  # no se llega
                raise AssertionError

        with pytest.raises(trabajos.CheckoutRechazado) as exc:
            await trabajos.ordenar(
                motor,
                parent_id,
                portador=acudiente,
                perfil="Ahorrador",
                entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
                correo="ana@example.com",
                comercio=ComercioRechaza(),
                catalogo=catalogo_simple(),
            )
        assert exc.value.estado == 422
        assert exc.value.cuerpo["error"] == "precio_cambiado"

    async def test_ordenar_un_trabajo_ajeno_se_rechaza_sin_tocar_comercio(self, motor):
        # El id del trabajo viaja en enlaces (/kits, /esperando): sin la sesion
        # de su dueno no se arma orden ni pago, ni anonimo ni con otra cuenta.
        await sembrar_canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=uuid.uuid4(),
            catalogo=catalogo_simple(),
        )
        parent_id = uuid.UUID(aplicado["trabajo_id"])

        class ComercioIntacto:
            async def crear_orden(self, cuerpo):  # no se llega
                raise AssertionError

            async def iniciar_pago(self, pedido_id, cuerpo):  # no se llega
                raise AssertionError

        for portador in (None, uuid.uuid4()):
            with pytest.raises(trabajos.CambioNoPermitido) as exc:
                await trabajos.ordenar(
                    motor,
                    parent_id,
                    portador=portador,
                    perfil="Ahorrador",
                    entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
                    correo="otra@example.com",
                    comercio=ComercioIntacto(),
                    catalogo=catalogo_simple(),
                )
            assert exc.value.estado == 403
            assert exc.value.codigo == "solicitud_ajena"


class TestElAcudienteCambiaSuKit:
    """El papa cambia un producto por una de sus alternativas, o se cambia de kit.

    Sus cambios se guardan en SU trabajo (`cambios`), nunca en las lineas del
    kit: esas lineas pueden ser el kit canonico del grado, el que reciben los
    demas acudientes por la ruta rapida.
    """

    async def _ruta_rapida(self, motor, usuario_id=None):
        canonico = await sembrar_canonico(motor)
        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=usuario_id,
            catalogo=catalogo_simple(),
        )
        return canonico, uuid.UUID(resultado["trabajo_id"])

    async def test_la_ruta_rapida_trae_los_kits_del_canonico_y_marca_el_elegido(self, motor):
        _, parent_id = await self._ruta_rapida(motor)
        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo_simple())
        # Sin personaje no hay Fan: solo los dos del canonico.
        assert [k["perfil"] for k in vista["kits"]] == ["Ahorrador", "Premium"]
        assert vista["recomendado"]["perfil"] == "Ahorrador"

    async def test_cambiar_por_una_alternativa_recalcula_y_no_toca_el_canonico(self, motor):
        canonico, parent_id = await self._ruta_rapida(motor)
        catalogo = catalogo_simple()
        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        cuaderno = linea_del_kit(vista, "Ahorrador", "2 cuadernos")
        assert cuaderno["producto_elegido"]["sku"] == "TK-C001-ECO"
        assert "TK-C001-PRE" in {a["sku"] for a in cuaderno["alternativas"]}
        total_antes = total_del_kit(vista, "Ahorrador")

        await trabajos.cambiar_producto_del_acudiente(
            motor,
            parent_id,
            "Ahorrador",
            uuid.UUID(cuaderno["item_id"]),
            "TK-C001-PRE",
            usuario_id=None,
            catalogo=catalogo,
        )

        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        cuaderno = linea_del_kit(vista, "Ahorrador", "2 cuadernos")
        assert cuaderno["producto_elegido"]["sku"] == "TK-C001-PRE"
        assert cuaderno["subtotal_linea"] == 2 * 12000
        # El que dejo pasa a ser una alternativa: siempre se puede volver.
        assert "TK-C001-ECO" in {a["sku"] for a in cuaderno["alternativas"]}
        assert total_del_kit(vista, "Ahorrador") == total_antes + 2 * (12000 - 4500)
        # El canonico sigue intacto para los demas acudientes.
        del_canonico = await trabajos.ver(motor, canonico, incluir_kits=True)
        assert (
            linea_del_kit(del_canonico, "Ahorrador", "2 cuadernos")["producto_elegido"]["sku"]
            == "TK-C001-ECO"
        )

    async def test_volver_al_original_borra_el_cambio(self, motor):
        _, parent_id = await self._ruta_rapida(motor)
        catalogo = catalogo_simple()
        item = uuid.UUID(
            linea_del_kit(
                await trabajos.ver(motor, parent_id, catalogo=catalogo), "Ahorrador", "2 cuadernos"
            )["item_id"]
        )
        for sku in ("TK-C001-PRE", "TK-C001-ECO"):
            await trabajos.cambiar_producto_del_acudiente(
                motor, parent_id, "Ahorrador", item, sku, usuario_id=None, catalogo=catalogo
            )
        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        assert linea_del_kit(vista, "Ahorrador", "2 cuadernos")["producto_elegido"]["sku"] == "TK-C001-ECO"
        assert vista["cambios"] == {}

    async def test_solo_se_puede_elegir_entre_las_alternativas_de_la_linea(self, motor):
        _, parent_id = await self._ruta_rapida(motor)
        catalogo = catalogo_simple()
        item = uuid.UUID(
            linea_del_kit(
                await trabajos.ver(motor, parent_id, catalogo=catalogo), "Ahorrador", "2 cuadernos"
            )["item_id"]
        )
        with pytest.raises(trabajos.CambioNoPermitido) as error:
            await trabajos.cambiar_producto_del_acudiente(
                motor, parent_id, "Ahorrador", item, "TK-C004-CON", usuario_id=None, catalogo=catalogo
            )
        assert error.value.codigo == "producto_no_permitido"

    async def test_la_solicitud_de_otro_acudiente_no_se_toca(self, motor):
        dueno = uuid.uuid4()
        _, parent_id = await self._ruta_rapida(motor, usuario_id=dueno)
        catalogo = catalogo_simple()
        item = uuid.UUID(
            linea_del_kit(
                await trabajos.ver(motor, parent_id, catalogo=catalogo), "Ahorrador", "2 cuadernos"
            )["item_id"]
        )
        with pytest.raises(trabajos.CambioNoPermitido) as error:
            await trabajos.cambiar_producto_del_acudiente(
                motor, parent_id, "Ahorrador", item, "TK-C001-PRE", usuario_id=uuid.uuid4(), catalogo=catalogo
            )
        assert error.value.codigo == "solicitud_ajena"
        await trabajos.cambiar_producto_del_acudiente(
            motor, parent_id, "Ahorrador", item, "TK-C001-PRE", usuario_id=dueno, catalogo=catalogo
        )

    async def test_en_un_kit_propio_tampoco_se_escriben_las_lineas(self, motor):
        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")
        vista = await trabajos.ver(motor, trabajo_id)
        item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])

        await trabajos.cambiar_producto_del_acudiente(
            motor, trabajo_id, "Ahorrador", item, "TK-C001-PRE", usuario_id=None, catalogo=catalogo
        )

        vista = await trabajos.ver(motor, trabajo_id)
        assert linea_del_kit(vista, "Ahorrador", "2 cuadernos")["producto_elegido"]["sku"] == "TK-C001-PRE"
        # La linea del Ahorrador en la base sigue con el economico: el cambio
        # vive en el trabajo, no en `linea_kit`.
        from sqlalchemy import select

        async with motor.engine.begin() as conexion:
            sku_en_base = await conexion.scalar(
                select(trabajos.LINEA.c.sku)
                .select_from(trabajos.LINEA.join(trabajos.KIT, trabajos.KIT.c.id == trabajos.LINEA.c.kit_id))
                .where(trabajos.LINEA.c.item_crudo_id == item, trabajos.KIT.c.perfil == "Ahorrador")
            )
        assert sku_en_base == "TK-C001-ECO"

    async def test_sin_publicar_no_se_cambia(self, motor):
        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)  # queda en revision
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])
        with pytest.raises(trabajos.CambioNoPermitido) as error:
            await trabajos.cambiar_producto_del_acudiente(
                motor, trabajo_id, "Ahorrador", item, "TK-C001-PRE", usuario_id=None, catalogo=catalogo
            )
        assert error.value.codigo == "kit_no_publicado"

    async def test_el_pago_usa_el_producto_que_eligio_el_papa(self, motor):
        dueno = uuid.uuid4()
        _, parent_id = await self._ruta_rapida(motor, usuario_id=dueno)
        catalogo = catalogo_simple()
        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        item = uuid.UUID(linea_del_kit(vista, "Premium", "2 cuadernos")["item_id"])
        # Se cambia de kit (Premium) y en ese kit baja el cuaderno al economico.
        await trabajos.cambiar_producto_del_acudiente(
            motor, parent_id, "Premium", item, "TK-C001-ECO", usuario_id=dueno, catalogo=catalogo
        )

        class ComercioFalso:
            orden = None

            async def crear_orden(self, cuerpo):
                self.orden = cuerpo
                return 201, {"pedido_id": "ped-1", "total": 0}

            async def iniciar_pago(self, pedido_id, cuerpo):
                return 201, {"pago_id": "pago-1", "url_redireccion": "https://pasarela/xy"}

        comercio = ComercioFalso()
        await trabajos.ordenar(
            motor,
            parent_id,
            portador=dueno,
            perfil="Premium",
            entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
            correo="ana@example.com",
            comercio=comercio,
            catalogo=catalogo,
        )
        skus = {linea["sku"] for linea in comercio.orden["lineas"]}
        assert "TK-C001-ECO" in skus and "TK-C001-PRE" not in skus


class TestLosPersonajesDelKitAplicado:
    async def test_parent_apply_nombra_al_hijo_de_las_lineas_no_canonico_fijo(self, motor):
        # Un canonico nacido de un preview: sus lineas dicen hijo "preview", no
        # "canonico". `personajes_por_hijo` debe usar la clave REAL de las lineas,
        # o la franja Fan de la web no casa y se queda vacia.
        catalogo = catalogo_simple()
        catalogo.respuestas["2 cuadernos cuadriculados"]["opciones"].append(
            opcion("TK-C001-FAN", "confiable", 9000, personaje="cars")
        )
        creado = await trabajos.crear(
            motor,
            hijos=[{"referencia": "preview", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            preferencias={},
            origen=trabajos.ORIGEN_CANONICO,
        )
        estado = await trabajos.procesar(motor, uuid.UUID(creado["trabajo_id"]), catalogo=catalogo)
        assert estado == EstadoTrabajo.PUBLICADO.value
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Fan",
            personaje="cars",
            catalogo=catalogo,
        )
        vista = await trabajos.ver(motor, uuid.UUID(aplicado["trabajo_id"]), catalogo=catalogo)
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")
        hijos_de_lineas = {linea["hijo"] for linea in fan["lineas"]}
        assert vista["personajes_por_hijo"] == {h: ["cars"] for h in hijos_de_lineas}

    async def test_unas_preferencias_ilegibles_no_tumban_la_vista(self, motor):
        # Una rotacion de llave o un VARIABLE_LLAVE mal puesto no debe tumbar ver()
        # (y con el, checkout, opciones y el chat): sin personajes, y sigue.
        from sqlalchemy import update

        trabajo_id, _ = await crear_y_procesar(
            motor, preferencias={"personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        )
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(trabajos.TRABAJO)
                .where(trabajos.TRABAJO.c.id == trabajo_id)
                .values(preferencias_cifradas=b"\x00\x01 esto no es un token valido")
            )

        vista = await trabajos.ver(motor, trabajo_id)
        assert vista["trabajo_id"] == str(trabajo_id)
        assert vista["personajes_por_hijo"] == {}


class TestElApodoEnLaRutaRapida:
    """El apodo es justo el dato que se guarda para nombrar al hijo en su kit. La
    ruta rapida (kit canonico) lo dejaba fuera del trabajo y el kit tenia que
    adivinarlo cruzando colegio y grado con las matriculas."""

    async def test_la_ruta_rapida_guarda_el_apodo_y_el_kit_lo_muestra(self, motor):
        from sqlalchemy import select

        await sembrar_canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            apodo="Tomi",
            usuario_id=uuid.uuid4(),
            catalogo=catalogo_simple(),
        )
        trabajo_id = uuid.UUID(aplicado["trabajo_id"])
        vista = await trabajos.ver(motor, trabajo_id, catalogo=catalogo_simple())
        assert vista["hijos"][0]["apodo"] == "Tomi"
        # La consola interna nunca recibe el apodo de un menor.
        admin = await trabajos.ver(motor, trabajo_id, catalogo=catalogo_simple(), incluir_admin=True)
        assert "apodo" not in admin["hijos"][0]
        # El pedido congelado (evento hacia Comercio) tampoco lo lleva.
        async with motor.engine.begin() as conexion:
            cargas = [
                e.carga
                for e in await conexion.execute(select(trabajos.BANDEJA))
                if e.tipo == "pedido_solicitado"
            ]
        assert cargas and "Tomi" not in str(cargas)

    async def test_sin_apodo_no_se_guarda_la_clave(self, motor):
        await sembrar_canonico(motor)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            catalogo=catalogo_simple(),
        )
        vista = await trabajos.ver(motor, uuid.UUID(aplicado["trabajo_id"]), catalogo=catalogo_simple())
        assert "apodo" not in vista["hijos"][0]
