from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from tukit_comun.bandeja import Resultado
from tukit_comun.mensajes import Evento
from tukit_inteligencia.modelos import ImportacionLista, ItemCrudo, Kit, TrabajoPipeline
from tukit_inteligencia.repositorios.trabajos import BANDEJA
from tukit_inteligencia.supresion import Supresor

TITULAR = uuid.uuid4()
OTRO = uuid.uuid4()
SOLICITUD = uuid.uuid4()
AHORA = datetime(2026, 10, 1, tzinfo=UTC)


async def _sembrar(motor, usuario_id: uuid.UUID, *, estado_importacion: str = "pendiente") -> uuid.UUID:
    tid = uuid.uuid4()
    async with motor.sesion() as db:
        db.add(
            TrabajoPipeline(
                id=tid,
                usuario_id=usuario_id,
                estado="publicado",
                hijos=[{"referencia": "hijo-1", "colegio_id": "C", "grado": "3"}],
                preferencias_cifradas=b"presupuesto-del-hogar",
            )
        )
        await db.flush()
        db.add(Kit(trabajo_id=tid, perfil="Ahorrador", total_cop=90_000, pesos_usados_cifrados=b"pesos"))
        db.add(ItemCrudo(trabajo_id=tid, hijo_referencia="hijo-1", orden=1, texto="2 cuadernos de 100 hojas"))
        db.add(
            ImportacionLista(
                subida_id=uuid.uuid4(),
                clave_idempotencia=uuid.uuid4(),
                referencias=["hijo-1"],
                contacto_referencia=str(usuario_id),
                colegio_id="C",
                grado="3",
                anio_lectivo=2026,
                carga={"items": ["x"], "preferencias": {"presupuesto": 200_000}},
                documento=b"%PDF foto de la lista con el nombre de Sofia",
                estado=estado_importacion,
                proximo_intento_en=AHORA,
            )
        )
    return tid


def _evento(id_: int = 7) -> Evento:
    return Evento(
        id=id_,
        origen="identidad",
        tipo="titular_suprimido",
        agregado_tipo="solicitud_supresion",
        agregado_id=SOLICITUD,
        carga={"usuario_id": str(TITULAR), "solicitud_id": str(SOLICITUD)},
    )


async def test_borra_preferencias_y_archivo_subido_y_conserva_el_kit(motor):
    tid = await _sembrar(motor, TITULAR)

    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO

    async with motor.sesion() as db:
        trabajo = await db.get(TrabajoPipeline, tid)
        assert trabajo.preferencias_cifradas is None
        assert trabajo.estado == "publicado"
        kit = (await db.execute(select(Kit))).scalar_one()
        assert kit.pesos_usados_cifrados is None
        assert (kit.perfil, kit.total_cop) == ("Ahorrador", 90_000)
        item = (await db.execute(select(ItemCrudo))).scalar_one()
        assert item.texto == "2 cuadernos de 100 hojas"
        importacion = (await db.execute(select(ImportacionLista))).scalar_one()
        assert importacion.documento is None
        assert importacion.carga is None
        assert importacion.contacto_referencia is None
        assert importacion.estado == "fallida"
        assert importacion.error == "titular_suprimido"


async def test_quita_el_apodo_de_los_hijos_y_conserva_el_resto(motor):
    tid = await _sembrar(motor, TITULAR)
    async with motor.sesion() as db:
        trabajo = await db.get(TrabajoPipeline, tid)
        trabajo.hijos = [
            {"referencia": "hijo-0", "colegio_id": "C", "grado": "3", "apodo": "Sofia"},
            {"referencia": "hijo-1", "colegio_id": "C", "grado": "3", "apodo": "Lucia"},
        ]

    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO

    async with motor.sesion() as db:
        trabajo = await db.get(TrabajoPipeline, tid)
        assert trabajo.hijos == [
            {"referencia": "hijo-0", "colegio_id": "C", "grado": "3"},
            {"referencia": "hijo-1", "colegio_id": "C", "grado": "3"},
        ]


async def test_una_importacion_ya_importada_conserva_su_estado(motor):
    await _sembrar(motor, TITULAR, estado_importacion="importada")

    await Supresor(motor).manejar(_evento())

    async with motor.sesion() as db:
        importacion = (await db.execute(select(ImportacionLista))).scalar_one()
        assert importacion.estado == "importada"
        assert importacion.documento is None


async def test_no_toca_lo_de_otro(motor):
    ajeno = await _sembrar(motor, OTRO)

    await Supresor(motor).manejar(_evento())

    async with motor.sesion() as db:
        assert (await db.get(TrabajoPipeline, ajeno)).preferencias_cifradas == b"presupuesto-del-hogar"
        importacion = (await db.execute(select(ImportacionLista))).scalar_one()
        assert importacion.documento is not None and importacion.estado == "pendiente"


async def test_confirma_una_sola_vez_aunque_el_evento_se_repita(motor):
    await _sembrar(motor, TITULAR)
    supresor = Supresor(motor)

    assert await supresor.manejar(_evento()) is Resultado.HECHO
    assert await supresor.manejar(_evento()) is Resultado.HECHO

    async with motor.engine.connect() as conexion:
        filas = (
            await conexion.execute(select(BANDEJA).where(BANDEJA.c.tipo == "supresion_confirmada"))
        ).all()
    assert len(filas) == 1
    assert filas[0].carga["servicio"] == "inteligencia"
    assert filas[0].agregado_id == SOLICITUD


async def test_un_evento_sin_el_id_de_solicitud_se_omite(motor):
    roto = Evento(id=2, origen="identidad", tipo="titular_suprimido", carga={"usuario_id": str(TITULAR)})
    assert await Supresor(motor).manejar(roto) is Resultado.OMITIR


async def test_borra_los_apodos_de_subidas_pendientes(motor):
    from tukit_inteligencia import apodos_subida

    await _sembrar(motor, TITULAR)
    await apodos_subida.guardar(motor, str(uuid.uuid4()), str(TITULAR), {"hijo-1": "Sofi"})
    version_otro = str(uuid.uuid4())
    await apodos_subida.guardar(motor, version_otro, str(OTRO), {"hijo-1": "Ana"})

    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO
    assert await apodos_subida.cuantos_de(motor, str(TITULAR)) == 0
    assert await apodos_subida.apodos_de(motor, version_otro) == {"hijo-1": "Ana"}
