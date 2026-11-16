"""El ciclo del trabajo en `trabajos.py`: crear, procesar, degradar y emitir.

Lo que estas pruebas defienden es que el estado del pipeline vive en la base
y no en el proceso. Es la propiedad que hace que `POST /v1/trabajos` pueda
devolver un 202 con sentido: si el estado no se persiste, el 202 promete un
identificador que despues nadie puede responder. La revision humana vive en
`test_revision_humana.py` y la ruta rapida del acudiente en
`test_aplicar_canonico.py`.
"""

from __future__ import annotations

import uuid

import pytest
from _ayudas_inteligencia import COLEGIO, catalogo_simple, crear_y_procesar
from conftest import CatalogoFalso, opcion
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido


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
        trabajo_id, estado = await crear_y_procesar(motor)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert {e["nombre"]: e["estado"] for e in vista["etapas"]} == {
            "percepcion": "ok",
            "normalizacion": "ok",
            "resolucion": "ok",
            "optimizacion": "ok",
        }
        assert {k["perfil"] for k in vista["kits"]} == {"Ahorrador", "Premium"}

    async def test_el_acudiente_no_ve_kits_antes_de_que_los_revisen(self, motor):
        """La razon de ser de `espera_revision` y de AD-06. El mismo lector
        con la bandera puesta si los devuelve, porque Admin tiene que verlos."""
        trabajo_id, _ = await crear_y_procesar(motor)

        assert (await trabajos.ver(motor, trabajo_id))["kits"] == []
        assert (await trabajos.ver(motor, trabajo_id))["recomendado"] is None
        assert len((await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]) == 2

    async def test_la_licencia_digital_sale_informativa_y_fuera_del_total(self, motor):
        trabajo_id, _ = await crear_y_procesar(motor)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")

        licencia = next(linea for linea in ahorrador["lineas"] if linea["informativa"])
        assert licencia["subtotal_linea"] is None
        assert licencia["instruccion_colegio"] == "Se adquiere con QUOVIX."
        # 2 cuadernos economicos a 4500 mas una caja de colores a 24900.
        assert ahorrador["total"] == 2 * 4500 + 24900

    async def test_el_renglon_que_el_catalogo_no_reconoce_queda_visible(self, motor):
        trabajo_id, _ = await crear_y_procesar(motor)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        lineas = kits[0]["lineas"]

        punzon = next(linea for linea in lineas if "punzon" in linea["descripcion"])
        assert punzon["estado_resolucion"] == EstadoResolucion.SIN_MATCH.value
        assert punzon["unidades_a_comprar"] == 0
        assert "producto_elegido" not in punzon

    async def test_los_candidatos_quedan_guardados_para_que_admin_pueda_elegir(self, motor):
        from sqlalchemy import func, select

        trabajo_id, _ = await crear_y_procesar(motor)
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
        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")
        total_antes = ahorrador["total"]
        cuaderno = next(
            linea for linea in ahorrador["lineas"] if linea["descripcion"].startswith("2 cuadernos")
        )
        assert cuaderno["producto_elegido"]["sku"] == "TK-C001-ECO"

        # Al premium: 2 cuadernos a 12000 en vez de 4500.
        await trabajos.fijar_producto_en_linea(
            motor,
            trabajo_id,
            "Ahorrador",
            uuid.UUID(cuaderno["item_id"]),
            "TK-C001-PRE",
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

    async def test_fijar_en_todos_pone_el_producto_en_cada_kit_y_lo_vuelve_comprable(self, motor):
        # El revisor resolvio un hueco («Diccionario Ingles – Ingles») y el
        # producto solo quedaba en el kit abierto; el «Broche de 9V» que era
        # informativo seguia diciendo «se compra por tu cuenta» con foto.
        from sqlalchemy import update

        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        cuaderno = next(
            linea for linea in kits[0]["lineas"] if linea["descripcion"].startswith("2 cuadernos")
        )
        item_id = uuid.UUID(cuaderno["item_id"])
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(trabajos.LINEA)
                .where(trabajos.LINEA.c.item_crudo_id == item_id)
                .values(informativa=True, sku=None, precio_unitario_cop=None, subtotal_cop=None)
            )

        respuesta = await trabajos.fijar_producto_en_todos_los_kits(
            motor, trabajo_id, item_id, "TK-C001-PRE", catalogo=catalogo
        )

        assert len(respuesta["perfiles"]) == len(kits)
        for kit in (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]:
            linea = next(x for x in kit["lineas"] if x["item_id"] == str(item_id))
            assert linea["producto_elegido"]["sku"] == "TK-C001-PRE", kit["perfil"]
            assert linea["informativa"] is False
            assert linea["subtotal_linea"] == 2 * 12000

    async def test_cambiar_el_producto_de_una_linea_ya_cubierta_no_la_vuelve_a_cobrar(self, motor):
        from sqlalchemy import update

        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        cuaderno = next(
            linea for linea in kits[0]["lineas"] if linea["descripcion"].startswith("2 cuadernos")
        )
        item_id = uuid.UUID(cuaderno["item_id"])
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(trabajos.LINEA)
                .where(trabajos.LINEA.c.item_crudo_id == item_id)
                .values(unidades_a_comprar=0, subtotal_cop=0, mensaje="Ya va en la linea 1.")
            )
        await trabajos.fijar_producto_en_linea(
            motor, trabajo_id, "Ahorrador", item_id, "TK-C001-PRE", catalogo=catalogo
        )
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        ahorrador = next(k for k in kits if k["perfil"] == "Ahorrador")
        linea = next(x for x in ahorrador["lineas"] if x["item_id"] == str(item_id))
        assert linea["unidades_a_comprar"] == 0
        assert linea["subtotal_linea"] == 0

    async def test_kit_o_item_inexistente_es_no_existe(self, motor):
        catalogo = catalogo_simple()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.fijar_producto_en_linea(
                motor,
                trabajo_id,
                "Ahorrador",
                uuid.uuid4(),
                "TK-C001-PRE",
                catalogo=catalogo,
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
        trabajo_id, estado = await crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id)

        assert estado == EstadoTrabajo.FALLIDO.value
        assert vista["error"] == "sin_lista_oficial"
        assert "Sube el archivo" in vista["mensaje"]

    async def test_el_catalogo_caido_deja_el_trabajo_reintentable(self, motor):
        class Caido(CatalogoFalso):
            async def listas(self, **kw):
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id, estado = await crear_y_procesar(motor, Caido())
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
        estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_simple())
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
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_simple())
        await trabajos.revisar(motor, trabajo_id, decision="devolver")
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_simple())

        async with motor.engine.begin() as conexion:
            items = await conexion.scalar(select(func.count()).select_from(trabajos.ITEM))
            kits = await conexion.scalar(select(func.count()).select_from(trabajos.KIT))
        assert items == 4
        assert kits == 2


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
        estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_simple())
        return trabajo_id, estado

    async def test_se_publica_sin_pasar_por_revision(self, motor):
        trabajo_id, estado = await self._crear_lista_verificada_y_procesar(motor)
        assert estado == EstadoTrabajo.PUBLICADO.value
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        assert vista["estado"] == EstadoTrabajo.PUBLICADO.value
        # Sin personaje ni `equilibrio` pedidos: Ahorrador y Premium (ADR 0030).
        assert [k["perfil"] for k in vista["kits"]] == ["Ahorrador", "Premium"]

    async def test_deja_kits_publicados_en_la_bandeja(self, motor):
        from sqlalchemy import select

        trabajo_id, _ = await self._crear_lista_verificada_y_procesar(motor)
        async with motor.engine.begin() as conexion:
            eventos = list(await conexion.execute(select(trabajos.BANDEJA)))
        assert [e.tipo for e in eventos] == ["kits_publicados"]
        assert eventos[0].agregado_id == trabajo_id


class TestElEventoLlevaTodasLasListas:
    async def test_evento_kits_publicados_lleva_todas_las_listas(self, motor):
        from sqlalchemy import insert, select
        from tukit_inteligencia.repositorios.trabajos import RepoTrabajos

        trabajo_id = uuid.uuid4()
        hijos = [
            {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Septimo", "apodo": "Sofi"},
            {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Jardin", "apodo": "Tomas"},
            # Un hermano en la misma lista no la repite.
            {"referencia": "hijo-3", "colegio_id": COLEGIO, "grado": "Jardin"},
        ]
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                insert(trabajos.TRABAJO).values(
                    id=trabajo_id, estado="publicado", hijos=hijos, usuario_id=uuid.uuid4()
                )
            )
            await RepoTrabajos(conexion).emitir_evento(trabajo_id)
        async with motor.engine.begin() as conexion:
            carga = (await conexion.execute(select(trabajos.BANDEJA.c.carga))).scalar_one()
        assert carga["listas"] == [
            {"colegio_id": COLEGIO, "grado": "Septimo"},
            {"colegio_id": COLEGIO, "grado": "Jardin"},
        ]
        # Compatibilidad con el repartidor de antes: el primer hijo sigue suelto.
        assert carga["colegio_id"] == COLEGIO and carga["grado"] == "Septimo"
        texto = str(carga)
        assert "referencia" not in texto and "apodo" not in texto
        assert "Sofi" not in texto and "hijo-1" not in texto


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


class TestElEventoOmiteAlHijoSinLista:
    async def test_evento_kits_publicados_omite_al_hijo_sin_lista(self, motor):
        from sqlalchemy import insert, select
        from tukit_inteligencia.modelos import Base
        from tukit_inteligencia.repositorios.trabajos import RepoTrabajos

        ITEM = Base.metadata.tables["item_crudo"]
        trabajo_id = uuid.uuid4()
        hijos = [
            {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Septimo"},
            # hijo-2 quedo en sin_lista: no tiene lineas, no debe ir al correo.
            {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Jardin"},
        ]
        kit_id, item_id = uuid.uuid4(), uuid.uuid4()
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                insert(trabajos.TRABAJO).values(
                    id=trabajo_id, estado="publicado", hijos=hijos, usuario_id=uuid.uuid4()
                )
            )
            await conexion.execute(
                insert(ITEM).values(
                    id=item_id, trabajo_id=trabajo_id, hijo_referencia="hijo-1", orden=1, texto="cuaderno"
                )
            )
            await conexion.execute(
                insert(trabajos.KIT).values(id=kit_id, trabajo_id=trabajo_id, perfil="Ahorrador")
            )
            await conexion.execute(
                insert(trabajos.LINEA).values(
                    id=uuid.uuid4(),
                    kit_id=kit_id,
                    item_crudo_id=item_id,
                    hijo_referencia="hijo-1",
                    orden=1,
                    descripcion="cuaderno",
                    estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
                )
            )
            await RepoTrabajos(conexion).emitir_evento(trabajo_id)
        async with motor.engine.begin() as conexion:
            carga = (await conexion.execute(select(trabajos.BANDEJA.c.carga))).scalar_one()
        assert carga["listas"] == [{"colegio_id": COLEGIO, "grado": "Septimo"}]
        assert carga["grado"] == "Septimo"
