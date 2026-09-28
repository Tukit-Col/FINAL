"""El ciclo completo del trabajo, sin red y sin Postgres.

Lo que estas pruebas defienden es que el estado del pipeline vive en la base
y no en el proceso. Es la propiedad que hace que `POST /v1/trabajos` pueda
devolver un 202 con sentido: si el estado no se persiste, el 202 promete un
identificador que despues nadie puede responder.
"""

from __future__ import annotations

import uuid

import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

COLEGIO = "11111111-1111-5111-8111-111111111111"


def _catalogo() -> CatalogoFalso:
    return CatalogoFalso(
        renglones=[
            renglon(1, "2 cuadernos cuadriculados", cantidad=2),
            renglon(2, "caja de colores x12"),
            renglon(
                3,
                "Plan lector virtual RAZ-PLUS",
                tipo_item="licencia_digital",
                modo_adquisicion="plataforma",
                instruccion_colegio="Se adquiere con QUOVIX.",
            ),
            renglon(4, "punzon punta metalica de titanio"),
        ],
        respuestas={
            "2 cuadernos cuadriculados": reconocido(
                "2 cuadernos cuadriculados",
                "C001",
                [
                    opcion("TK-C001-ECO", "economico", 4500),
                    opcion("TK-C001-PRE", "premium", 12000),
                ],
            ),
            "caja de colores x12": reconocido(
                "caja de colores x12",
                "C004",
                [opcion("TK-C004-CON", "confiable", 24900, unidades_por_empaque=12)],
            ),
        },
    )


async def _crear_y_procesar(motor, catalogo=None, preferencias=None):
    catalogo = catalogo or _catalogo()
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias=preferencias or {},
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo)
    return trabajo_id, estado


class TestElTrabajoNaceConsultable:
    async def test_se_crea_encolado_y_con_las_cuatro_etapas_pendientes(self, motor):
        respuesta = await trabajos.crear(
            motor, hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}]
        )
        vista = await trabajos.ver(motor, uuid.UUID(respuesta["trabajo_id"]))

        assert respuesta["estado"] == EstadoTrabajo.ENCOLADO.value
        assert respuesta["consultar_en"].endswith(respuesta["trabajo_id"])
        assert [e["nombre"] for e in vista["etapas"]] == [
            "percepcion",
            "normalizacion",
            "resolucion",
            "optimizacion",
        ]
        assert all(e["estado"] == "pendiente" for e in vista["etapas"])

    async def test_las_preferencias_no_quedan_legibles_en_la_columna(self, motor):
        """No es criptografia de verdad todavia, pero si el puerto. Lo que se
        comprueba es que el dato pasa por el cifrador y vuelve entero."""
        from sqlalchemy import select
        from tukit_comun.cifrado import cifrador_desde_entorno

        respuesta = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            preferencias={"presupuesto_por_hijo": 700000},
        )
        async with motor.engine.begin() as conexion:
            guardado = await conexion.scalar(
                select(trabajos.TRABAJO.c.preferencias_cifradas).where(
                    trabajos.TRABAJO.c.id == uuid.UUID(respuesta["trabajo_id"])
                )
            )
        assert isinstance(guardado, bytes)
        assert cifrador_desde_entorno().descifrar_json(guardado) == {"presupuesto_por_hijo": 700000}


class TestElPipelineDejaTresKits:
    async def test_corre_las_cuatro_etapas_y_queda_esperando_revision(self, motor):
        trabajo_id, estado = await _crear_y_procesar(motor)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert {e["nombre"]: e["estado"] for e in vista["etapas"]} == {
            "percepcion": "ok",
            "normalizacion": "ok",
            "resolucion": "ok",
            "optimizacion": "ok",
        }
        assert {k["perfil"] for k in vista["kits"]} == {"Ahorrador", "Fan", "Premium"}

    async def test_el_acudiente_no_ve_kits_antes_de_que_los_revisen(self, motor):
        """La razon de ser de `espera_revision` y de AD-06. El mismo lector
        con la bandera puesta si los devuelve, porque Admin tiene que verlos."""
        trabajo_id, _ = await _crear_y_procesar(motor)

        assert (await trabajos.ver(motor, trabajo_id))["kits"] == []
        assert (await trabajos.ver(motor, trabajo_id))["recomendado"] is None
        assert len((await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]) == 3

    async def test_la_licencia_digital_sale_informativa_y_fuera_del_total(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")

        licencia = next(linea for linea in ahorrador["lineas"] if linea["informativa"])
        assert licencia["subtotal_linea"] is None
        assert licencia["instruccion_colegio"] == "Se adquiere con QUOVIX."
        # 2 cuadernos economicos a 4500 mas una caja de colores a 24900.
        assert ahorrador["total"] == 2 * 4500 + 24900

    async def test_el_renglon_que_el_catalogo_no_reconoce_queda_visible(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        lineas = kits[0]["lineas"]

        punzon = next(linea for linea in lineas if "punzon" in linea["descripcion"])
        assert punzon["estado_resolucion"] == EstadoResolucion.SIN_MATCH.value
        assert punzon["unidades_a_comprar"] == 0
        assert "producto_elegido" not in punzon

    async def test_los_candidatos_quedan_guardados_para_que_admin_pueda_elegir(self, motor):
        from sqlalchemy import func, select

        trabajo_id, _ = await _crear_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            total = await conexion.scalar(select(func.count()).select_from(trabajos.CANDIDATO))
        # Dos del cuaderno y uno de los colores.
        assert total == 3


class TestFijarProductoPorNivel:
    """Fijar un producto escribe LINEA de UN kit y recalcula su total.

    Es la ruta que faltaba: antes solo se escribia RESOLUCION (por item, los
    tres kits a la vez) y el producto elegido nunca llegaba al kit publicado.
    """

    async def test_fijar_cambia_solo_ese_kit_y_recalcula_el_total(self, motor):
        catalogo = _catalogo()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")
        total_antes = ahorrador["total"]
        cuaderno = next(
            linea for linea in ahorrador["lineas"] if linea["descripcion"].startswith("2 cuadernos")
        )
        assert cuaderno["producto_elegido"]["sku"] == "TK-C001-ECO"

        # Al premium: 2 cuadernos a 12000 en vez de 4500.
        await trabajos.fijar_producto_en_linea(
            motor, trabajo_id, "Ahorrador", uuid.UUID(cuaderno["item_id"]), "TK-C001-PRE",
            catalogo=catalogo,
        )

        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")
        cuaderno = next(
            linea for linea in ahorrador["lineas"] if linea["descripcion"].startswith("2 cuadernos")
        )
        assert cuaderno["producto_elegido"]["sku"] == "TK-C001-PRE"
        assert cuaderno["subtotal_linea"] == 2 * 12000
        assert ahorrador["total"] == total_antes + 2 * (12000 - 4500)

    async def test_kit_o_item_inexistente_es_no_existe(self, motor):
        catalogo = _catalogo()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.fijar_producto_en_linea(
                motor, trabajo_id, "Ahorrador", uuid.uuid4(), "TK-C001-PRE", catalogo=catalogo,
            )


class TestLaTraduccionDeEstados:
    """`abstencion` del catalogo es `HUECO_CATALOGO` y no `SIN_MATCH`.

    Es la distincion que permite decir "te entendi y no lo tengo" en vez de
    "no te entendi", y solo la primera se puede responder con una
    alternativa.
    """

    @pytest.mark.parametrize(
        ("estado_catalogo", "esperado"),
        [
            ("hueco_catalogo", EstadoResolucion.HUECO_CATALOGO.value),
            ("abstencion", EstadoResolucion.HUECO_CATALOGO.value),
            ("sin_match", EstadoResolucion.SIN_MATCH.value),
        ],
    )
    def test_traduce_al_vocabulario_del_contrato(self, estado_catalogo, esperado):
        assert (
            trabajos.estado_desde_emparejamiento({"estado": estado_catalogo, "opciones": []}, 0.75)
            == esperado
        )

    def test_reconocido_por_debajo_del_umbral_es_ambiguo(self):
        respuesta = {"estado": "reconocido", "parecido": 0.6, "opciones": [opcion("X", "economico", 1)]}
        assert trabajos.estado_desde_emparejamiento(respuesta, 0.75) == EstadoResolucion.AMBIGUO.value

    def test_reconocido_sin_opciones_es_un_hueco_y_no_un_acierto(self):
        respuesta = {"estado": "reconocido", "parecido": 0.99, "opciones": []}
        assert trabajos.estado_desde_emparejamiento(respuesta, 0.75) == EstadoResolucion.HUECO_CATALOGO.value


class TestDegradarNuncaTumbar:
    async def test_sin_lista_oficial_el_trabajo_falla_con_diagnostico(self, motor):
        catalogo = CatalogoFalso(grado="Septimo")
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id)

        assert estado == EstadoTrabajo.FALLIDO.value
        assert vista["error"] == "sin_lista_oficial"
        assert "Sube el archivo" in vista["mensaje"]

    async def test_el_catalogo_caido_deja_el_trabajo_reintentable(self, motor):
        class Caido(CatalogoFalso):
            async def listas(self, **kw):
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id, estado = await _crear_y_procesar(motor, Caido())
        vista = await trabajos.ver(motor, trabajo_id)

        assert estado == EstadoTrabajo.FALLIDO.value
        assert vista["error"] == "dependencia_caida"
        assert "se puede reintentar" in vista["mensaje"]

    async def test_un_hijo_sin_lista_degrada_percepcion_pero_no_tumba(self, motor):
        # Caracterizacion (I-2): con DOS hijos donde solo uno tiene lista
        # publicada, el trabajo NO falla —el otro hijo aporta renglones— pero
        # la etapa percepcion queda DEGRADADA, no OK: la seccion 8 exige decir
        # que falto en vez de fingir un kit completo. Es la rama
        # `detalle["sin_lista"]` de procesar que ningun test cubria.
        respuesta = await trabajos.crear(
            motor,
            hijos=[
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Septimo"},
            ],
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        estado = await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        vista = await trabajos.ver(motor, trabajo_id)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        percepcion = next(e for e in vista["etapas"] if e["nombre"] == "percepcion")
        assert percepcion["estado"] == "degradada"
        assert [s["hijo"] for s in percepcion["detalle"]["sin_lista"]] == ["hijo-2"]

    async def test_reprocesar_no_duplica_items_ni_kits(self, motor):
        from sqlalchemy import func, select

        respuesta = await trabajos.crear(
            motor, hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}]
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        await trabajos.revisar(motor, trabajo_id, decision="devolver")
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        async with motor.engine.begin() as conexion:
            items = await conexion.scalar(select(func.count()).select_from(trabajos.ITEM))
            kits = await conexion.scalar(select(func.count()).select_from(trabajos.KIT))
        assert items == 4
        assert kits == 3


class TestPublicarDirectoDesdeListaVerificada:
    """Caracterizacion (I-2) del `publicar_directo`: un trabajo con
    origen='lista_verificada' (el kit del padre cuya lista un admin ya aprobo)
    se publica SIN pasar por la cola de revision y deja `kits_publicados` en la
    MISMA transaccion que el cambio a PUBLICADO. Es la rama de _finalizar que
    solo cubria el preview (por la negativa) y `revisar` (por la ruta manual)."""

    async def _crear_lista_verificada_y_procesar(self, motor):
        respuesta = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            origen="lista_verificada",
            usuario_id=uuid.uuid4(),
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        estado = await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        return trabajo_id, estado

    async def test_se_publica_sin_pasar_por_revision(self, motor):
        trabajo_id, estado = await self._crear_lista_verificada_y_procesar(motor)
        assert estado == EstadoTrabajo.PUBLICADO.value
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        assert vista["estado"] == EstadoTrabajo.PUBLICADO.value
        assert len(vista["kits"]) == 3

    async def test_deja_kits_publicados_en_la_bandeja(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await self._crear_lista_verificada_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            eventos = list(await conexion.execute(select(trabajos.BANDEJA)))
        assert [e.tipo for e in eventos] == ["kits_publicados"]
        assert eventos[0].agregado_id == trabajo_id


class TestElEventoDeOutboxNoEsDualWrite:
    """I3.d: `emitir_evento` no abre transaccion propia. Si el orquestador hace
    rollback despues de emitirlo, la fila de la bandeja NO debe sobrevivir: eso
    es lo que separa un outbox transaccional de un dual-write que deja eventos
    huerfanos que el repartidor reintenta sin fin."""

    async def test_la_fila_no_sobrevive_a_un_rollback_a_mitad(self, motor):
        from sqlalchemy import func, select

        from tukit_inteligencia.repositorios.trabajos import RepoTrabajos

        trabajo_id = uuid.uuid4()
        # Se emite el evento y se ABORTA la transaccion (rollback) sin commit:
        # begin() hace rollback si el bloque sale por excepcion.
        with pytest.raises(RuntimeError):
            async with motor.engine.begin() as conexion:
                await RepoTrabajos(conexion).emitir_evento(trabajo_id)
                raise RuntimeError("aborta a mitad")

        async with motor.engine.begin() as conexion:
            cuantos = await conexion.scalar(select(func.count()).select_from(trabajos.BANDEJA))
        assert cuantos == 0


class TestLaRevisionHumana:
    async def test_aprobar_publica_y_deja_el_evento_en_la_bandeja(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await _crear_y_procesar(motor)
        actor = uuid.uuid4()
        resultado = await trabajos.revisar(motor, trabajo_id, decision="aprobar", nota="ok", actor=actor)

        vista = await trabajos.ver(motor, trabajo_id)
        assert resultado["estado"] == EstadoTrabajo.PUBLICADO.value
        assert vista["estado"] == EstadoTrabajo.PUBLICADO.value
        assert len(vista["kits"]) == 3
        assert vista["recomendado"]["perfil"] == "Ahorrador"

        async with motor.engine.begin() as conexion:
            eventos = list(await conexion.execute(select(trabajos.BANDEJA)))
        assert [e.tipo for e in eventos] == ["kits_publicados"]

    async def test_publicar_dos_veces_no_se_puede(self, motor):
        """No es idempotente: es un segundo aviso al acudiente."""
        trabajo_id, _ = await _crear_y_procesar(motor)
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
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        with pytest.raises(trabajos.PreviewNoPublicable):
            await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        # No se emitio ningun evento sin destinatario.
        async with motor.engine.begin() as conexion:
            eventos = await conexion.scalar(select(func.count()).select_from(trabajos.BANDEJA))
        assert eventos == 0

    async def test_borrar_un_trabajo_en_revision_lo_saca_de_la_cola(self, motor):
        from sqlalchemy import func, select

        trabajo_id, _ = await _crear_y_procesar(motor)
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
        trabajo_id, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        with pytest.raises(trabajos.TrabajoProtegido):
            await trabajos.eliminar(motor, trabajo_id)

        # Sigue vivo y publicado.
        assert (await trabajos.ver(motor, trabajo_id))["estado"] == EstadoTrabajo.PUBLICADO.value

    async def test_borrar_uno_que_no_existe_es_TrabajoNoExiste(self, motor):
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.eliminar(motor, uuid.uuid4())

    async def test_publicar_deja_el_puntero_canonico_del_grado(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        async with motor.engine.begin() as conexion:
            puntero = list(await conexion.execute(select(trabajos.KIT_CANONICO)))
        assert len(puntero) == 1
        assert puntero[0].colegio_id == COLEGIO
        assert puntero[0].grado == "Cuarto"
        assert puntero[0].trabajo_id == trabajo_id

    async def test_republicar_el_mismo_grado_reemplaza_el_puntero(self, motor):
        from sqlalchemy import select

        primero, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, primero, decision="aprobar")
        segundo, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, segundo, decision="aprobar")

        async with motor.engine.begin() as conexion:
            puntero = list(await conexion.execute(select(trabajos.KIT_CANONICO)))
        # Una sola cache bendita por grado: el segundo desbanca al primero.
        assert len(puntero) == 1
        assert puntero[0].trabajo_id == segundo


class TestAplicarCanonico:
    """La ruta rapida del acudiente: sin re-optimizar, sin cola, un pedido."""

    async def test_aplicar_no_copia_kits_y_congela_el_pedido(self, motor):
        from sqlalchemy import func, select

        canonico, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, canonico, decision="aprobar")

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
            catalogo=_catalogo(),
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
        catalogo = _catalogo()
        catalogo.respuestas["2 cuadernos cuadriculados"]["opciones"].append(
            opcion("TK-C001-FAN", "confiable", 9000, personaje="cars")
        )
        canonico, _ = await _crear_y_procesar(motor, catalogo=catalogo)
        await trabajos.revisar(motor, canonico, decision="aprobar")

        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
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
                catalogo=_catalogo(),
            )

    async def test_ver_sigue_el_puntero_y_pinta_el_kit_con_personaje(self, motor):
        # ver() de un parent_apply no tiene kits propios: sigue el puntero al
        # canonico y arma el unico kit del perfil, con el personaje en el ancla.
        catalogo = _catalogo()
        catalogo.respuestas["2 cuadernos cuadriculados"]["opciones"].append(
            opcion("TK-C001-FAN", "confiable", 9000, personaje="cars")
        )
        canonico, _ = await _crear_y_procesar(motor, catalogo=catalogo)
        await trabajos.revisar(motor, canonico, decision="aprobar")

        resultado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            personaje="cars",
            catalogo=catalogo,
        )
        parent_id = uuid.UUID(resultado["trabajo_id"])

        vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
        assert len(vista["kits"]) == 1
        assert vista["kits"][0]["perfil"] == "Ahorrador"
        assert vista["kits"][0]["total"] == resultado["total"]
        c001 = next(linea for linea in vista["kits"][0]["lineas"] if linea.get("concepto") == "C001")
        assert c001["producto_elegido"]["sku"] == "TK-C001-FAN"

    async def test_ordenar_arma_la_orden_server_to_server_sin_ids_de_base(self, motor):
        # El checkout: del kit publicado a la orden. Se verifica que Inteligencia
        # manda a Comercio SOLO sku+precio (nunca un id canonico: RPO cero) y que
        # devuelve la url de la pasarela para mandar al acudiente a pagar.
        canonico, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, canonico, decision="aprobar")
        aplicado = await trabajos.aplicar_canonico(
            motor, colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026,
            perfil="Ahorrador", usuario_id=uuid.uuid4(), catalogo=_catalogo(),
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
            motor, parent_id, perfil="Ahorrador",
            entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
            correo="ana@example.com", comercio=comercio, catalogo=_catalogo(),
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
        canonico, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, canonico, decision="aprobar")
        aplicado = await trabajos.aplicar_canonico(
            motor, colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026,
            perfil="Ahorrador", usuario_id=uuid.uuid4(), catalogo=_catalogo(),
        )
        parent_id = uuid.UUID(aplicado["trabajo_id"])

        class ComercioRechaza:
            async def crear_orden(self, cuerpo):
                return 422, {"error": "precio_cambiado", "mensaje": "cambio"}
            async def iniciar_pago(self, pedido_id, cuerpo):  # no se llega
                raise AssertionError

        with pytest.raises(trabajos.CheckoutRechazado) as exc:
            await trabajos.ordenar(
                motor, parent_id, perfil="Ahorrador",
                entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
                correo="ana@example.com", comercio=ComercioRechaza(), catalogo=_catalogo(),
            )
        assert exc.value.estado == 422
        assert exc.value.cuerpo["error"] == "precio_cambiado"

    async def test_la_cola_lista_lo_que_espera_a_una_persona(self, motor):
        await _crear_y_procesar(motor)
        cola = await trabajos.cola(motor)

        assert cola["total"] == 1
        # El punzon quedo sin match y la licencia no pasa por el catalogo.
        assert cola["trabajos"][0]["lineas_a_revisar"] == 1

    async def test_validar_una_linea_deja_quien_y_cuando(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await _crear_y_procesar(motor)
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
