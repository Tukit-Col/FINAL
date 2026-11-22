from __future__ import annotations

import uuid

from sqlalchemy import insert
from tukit_inteligencia.metricas import metricas_de_colegio
from tukit_inteligencia.modelos import Base, EstadoResolucion, EstadoTrabajo

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]
ITEM = Base.metadata.tables["item_crudo"]

COLEGIO = "22222222-2222-5222-8222-222222222222"
OTRO_COLEGIO = "33333333-3333-5333-8333-333333333333"


async def _sembrar_trabajo(
    motor,
    colegio_id: str,
    *,
    estado: str = EstadoTrabajo.PUBLICADO.value,
    lineas: list[tuple[str, bool]],
    ahorro: int = 0,
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    kit_id = uuid.uuid4()
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id,
                estado=estado,
                origen="colegio_grado",
                hijos=[{"referencia": "hijo-1", "colegio_id": colegio_id, "grado": "Primero"}],
            )
        )
        await conexion.execute(
            insert(KIT).values(
                id=kit_id,
                trabajo_id=trabajo_id,
                perfil="Ahorrador",
                total_cop=10000,
                recomendado=True,
                consolidaciones=[{"sku": "X", "ahorro": ahorro}] if ahorro else [],
            )
        )
        for i, (estado_res, informativa) in enumerate(lineas):
            item_id = uuid.uuid4()
            await conexion.execute(
                insert(ITEM).values(
                    id=item_id,
                    trabajo_id=trabajo_id,
                    hijo_referencia="hijo-1",
                    orden=i,
                    texto=f"item {i}",
                )
            )
            await conexion.execute(
                insert(LINEA).values(
                    id=uuid.uuid4(),
                    kit_id=kit_id,
                    item_crudo_id=item_id,
                    hijo_referencia="hijo-1",
                    orden=i,
                    descripcion=f"item {i}",
                    estado_resolucion=estado_res,
                    informativa=informativa,
                )
            )
    return trabajo_id


async def test_colegio_sin_trabajos_da_ceros(motor):
    metricas = await metricas_de_colegio(motor, COLEGIO)
    assert metricas == {
        "colegio_id": COLEGIO,
        "kits_armados": 0,
        "lineas_comprables": 0,
        "lineas_resueltas": 0,
        "cobertura": 0.0,
        "ahorro_total_cop": 0,
    }


async def test_cuenta_kits_cobertura_y_ahorro(motor):
    await _sembrar_trabajo(
        motor,
        COLEGIO,
        lineas=[
            (EstadoResolucion.RESUELTO_AUTO.value, False),
            (EstadoResolucion.AMBIGUO.value, False),
            (EstadoResolucion.HUECO_CATALOGO.value, True),
        ],
        ahorro=2500,
    )
    metricas = await metricas_de_colegio(motor, COLEGIO)
    assert metricas["kits_armados"] == 1
    assert metricas["lineas_comprables"] == 2
    assert metricas["lineas_resueltas"] == 1
    assert metricas["cobertura"] == 0.5
    assert metricas["ahorro_total_cop"] == 2500


async def test_ignora_no_publicados_y_otros_colegios(motor):
    await _sembrar_trabajo(motor, COLEGIO, lineas=[(EstadoResolucion.RESUELTO_AUTO.value, False)])
    await _sembrar_trabajo(
        motor,
        COLEGIO,
        estado=EstadoTrabajo.ESPERA_REVISION.value,
        lineas=[(EstadoResolucion.RESUELTO_AUTO.value, False)],
    )
    await _sembrar_trabajo(motor, OTRO_COLEGIO, lineas=[(EstadoResolucion.RESUELTO_AUTO.value, False)])

    metricas = await metricas_de_colegio(motor, COLEGIO)
    assert metricas["kits_armados"] == 1
    assert metricas["lineas_comprables"] == 1
