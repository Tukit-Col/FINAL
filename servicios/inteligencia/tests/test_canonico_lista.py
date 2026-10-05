"""Los kits canonicos nacen con la lista aprobada, no con el primer padre.

Antes la cache canonica de un (colegio, grado, anio) solo se llenaba al publicar
el trabajo de un acudiente: el primer padre de cada grado pagaba el optimizador
y, si nadie subia nada, el grado nunca tenia ruta rapida. Ahora:

- Aprobar una lista emite `lista_aprobada`; el poller arma los tres kits sin
  preferencias (`origen='canonico_lista'`), los publica SIN avisar a nadie y
  fija el puntero canonico.
- Si el admin aprobo desde el preview, ese preview —con sus ajustes— queda como
  canonico (`fijar_como_canonico`) y el poller no vuelve a optimizar esa
  version.
- El trabajo de un acudiente no se puede fijar como canonico: lleva sus
  preferencias y su tope.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import MetaData, insert, select
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_comun.bandeja import bandeja_reflejada
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.poller import Poller

BANDEJA_CATALOGO = bandeja_reflejada(MetaData())
GRADO = "Cuarto"


async def _evento_lista_aprobada(motor, version_id: uuid.UUID) -> None:
    async with motor.engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
        await conexion.execute(
            insert(BANDEJA_CATALOGO).values(
                tipo="lista_aprobada",
                agregado_tipo="version_lista_oficial",
                agregado_id=version_id,
                carga={"colegio_id": COLEGIO, "grado": GRADO, "anio_lectivo": 2026},
                intentos=0,
            )
        )


async def _preview(motor, version_id: uuid.UUID) -> uuid.UUID:
    """Un preview de onboarding ya procesado, en `espera_revision`."""
    creado = await trabajos.crear(
        motor,
        hijos=[
            {
                "referencia": "preview",
                "colegio_id": COLEGIO,
                "grado": GRADO,
                "anio_lectivo": 2026,
                "version_id": str(version_id),
            }
        ],
        contacto=None,
        preferencias={},
        origen="preview_onboarding",
    )
    trabajo_id = uuid.UUID(creado["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo_verificado())
    assert estado == EstadoTrabajo.ESPERA_REVISION.value
    return trabajo_id


async def _puntero(motor) -> Any:
    async with motor.engine.begin() as conexion:
        return (
            await conexion.execute(
                select(trabajos.KIT_CANONICO.c.trabajo_id).where(
                    trabajos.KIT_CANONICO.c.colegio_id == COLEGIO,
                    trabajos.KIT_CANONICO.c.grado == GRADO,
                )
            )
        ).scalar_one_or_none()


async def _avisos(motor) -> list[Any]:
    async with motor.engine.begin() as conexion:
        return list(
            await conexion.execute(
                select(trabajos.BANDEJA.c.id).where(trabajos.BANDEJA.c.tipo == "kits_publicados")
            )
        )


class TestListaAprobadaArmaLosCanonicos:
    async def test_el_poller_arma_publica_sin_avisar_y_fija_el_puntero(self, motor):
        await _evento_lista_aprobada(motor, uuid.uuid4())
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=_catalogo_verificado()
        )

        assert await poller.pasada() == 1

        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        trabajos.TRABAJO.c.id,
                        trabajos.TRABAJO.c.estado,
                        trabajos.TRABAJO.c.origen,
                        trabajos.TRABAJO.c.usuario_id,
                    )
                )
            ).one()
        assert fila.origen == trabajos.ORIGEN_CANONICO
        assert fila.estado == EstadoTrabajo.PUBLICADO.value
        assert fila.usuario_id is None
        assert await _puntero(motor) == fila.id
        # Nadie a quien avisar: el repartidor no debe recibir nada.
        assert await _avisos(motor) == []

    async def test_una_version_que_ya_tiene_canonico_no_se_vuelve_a_optimizar(self, motor):
        version = uuid.uuid4()
        preview = await _preview(motor, version)
        await trabajos.fijar_como_canonico(motor, preview)

        await _evento_lista_aprobada(motor, version)
        catalogo = _catalogo_verificado()
        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)

        assert await poller.pasada() == 0
        assert "resueltos" not in catalogo.llamadas
        assert await _puntero(motor) == preview

    async def test_si_el_preview_se_fija_mientras_optimiza_el_preview_gana(self, motor):
        # Carrera: el poller arranca antes de que el admin fije el preview. Al
        # cerrar, el canonico_lista ve que su version ya tiene canonico y se
        # retira en vez de pisar el puntero.
        version = uuid.uuid4()
        preview = await _preview(motor, version)
        creado = await trabajos.crear(
            motor,
            hijos=[
                {
                    "referencia": "canonico",
                    "colegio_id": COLEGIO,
                    "grado": GRADO,
                    "anio_lectivo": 2026,
                    "version_id": str(version),
                }
            ],
            preferencias={},
            origen=trabajos.ORIGEN_CANONICO,
        )
        await trabajos.fijar_como_canonico(motor, preview)

        estado = await trabajos.procesar(
            motor, uuid.UUID(creado["trabajo_id"]), catalogo=_catalogo_verificado()
        )

        assert estado == "descartado"
        assert await _puntero(motor) == preview


class TestFijarComoCanonico:
    async def test_un_preview_queda_publicado_y_canonico_sin_aviso(self, motor):
        preview = await _preview(motor, uuid.uuid4())

        resultado = await trabajos.fijar_como_canonico(motor, preview, nota="revisado")

        assert resultado["estado"] == EstadoTrabajo.PUBLICADO.value
        assert await _puntero(motor) == preview
        assert await _avisos(motor) == []
        # Y como es publicado, re-previsualizar no lo borra.
        assert await trabajos.previews_de(motor, COLEGIO, GRADO, 2026) == []

    async def test_el_trabajo_de_un_acudiente_no_se_fija_como_canonico(self, motor):
        creado = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": GRADO}],
            preferencias={},
            usuario_id=uuid.uuid4(),
        )
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo_verificado())

        with pytest.raises(trabajos.NoCanonizable):
            await trabajos.fijar_como_canonico(motor, trabajo_id)
        assert await _puntero(motor) is None
