"""El cruce `pedido pagado -> trabajo -> hijos -> padre` de un colegio.

`resumen_pedidos_de_colegio` no sale a la red: recibe un doble de Comercio que
devuelve los pedidos pagados en memoria (mismos que devolvería
`GET /v1/comercio/pedidos-pagados`) y cruza contra `trabajo_pipeline` sembrado en
el SQLite del conftest. Se comprueba: conteo por colegio, por grado y por padre;
que solo entran los pagados; el dedupe por trabajo; y los estados de trabajo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import insert
from tukit_inteligencia.metricas import resumen_pedidos_de_colegio
from tukit_inteligencia.modelos import Base, EstadoTrabajo

TRABAJO = Base.metadata.tables["trabajo_pipeline"]

COLEGIO = "22222222-2222-5222-8222-222222222222"
OTRO_COLEGIO = "33333333-3333-5333-8333-333333333333"


@dataclass
class ComercioFalso:
    """Implementación en memoria del puerto hacia Comercio: solo `pedidos_pagados`."""

    pagados: list[dict[str, Any]] = field(default_factory=list)

    async def pedidos_pagados(self) -> list[dict[str, Any]]:
        return self.pagados


async def _sembrar_trabajo(
    motor,
    *,
    estado: str = EstadoTrabajo.PUBLICADO.value,
    hijos: list[dict[str, Any]],
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    # El CHECK del modelo exige diagnóstico si el trabajo quedó fallido.
    error = "prueba" if estado == EstadoTrabajo.FALLIDO.value else None
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id, estado=estado, origen="colegio_grado", hijos=hijos, error=error
            )
        )
    return trabajo_id


def _pagado(trabajo_id: uuid.UUID, usuario_id: str) -> dict[str, Any]:
    return {"trabajo_id": str(trabajo_id), "usuario_id": usuario_id, "estado": "pagado"}


async def test_cuenta_por_colegio_ignorando_otros(motor):
    # Un trabajo con un hijo en el colegio pedido y otro en otro colegio: solo el
    # primero cuenta.
    t = await _sembrar_trabajo(
        motor,
        hijos=[
            {"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"},
            {"referencia": "h2", "colegio_id": OTRO_COLEGIO, "grado": "Quinto"},
        ],
    )
    comercio = ComercioFalso([_pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_padres"] == 1
    assert resumen["total_ninos"] == 1
    assert resumen["por_padre"] == [{"usuario_id": "padre-1", "ninos": 1}]


async def test_por_grado_y_por_padre(motor):
    # Un padre con dos hijos de Quinto en el colegio: suma 2 en Quinto.
    t = await _sembrar_trabajo(
        motor,
        hijos=[
            {"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"},
            {"referencia": "h2", "colegio_id": COLEGIO, "grado": "Quinto"},
        ],
    )
    comercio = ComercioFalso([_pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_ninos"] == 2
    quinto = next(g for g in resumen["por_grado"] if g["grado"] == "Quinto")
    assert quinto["padres"] == 1
    assert quinto["ninos"] == 2
    assert quinto["por_padre"] == [{"usuario_id": "padre-1", "ninos": 2}]


async def test_solo_pedidos_pagados_entran(motor):
    pagado = await _sembrar_trabajo(
        motor, hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}]
    )
    # Este trabajo existe y es del colegio, pero NO tiene pedido pagado.
    await _sembrar_trabajo(motor, hijos=[{"referencia": "h9", "colegio_id": COLEGIO, "grado": "Cuarto"}])
    comercio = ComercioFalso([_pagado(pagado, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_padres"] == 1
    assert resumen["total_ninos"] == 1
    assert [g["grado"] for g in resumen["por_grado"]] == ["Quinto"]


async def test_dedupe_por_trabajo(motor):
    # El mismo trabajo con dos pedidos pagados (re-pedido) cuenta sus niños UNA vez.
    t = await _sembrar_trabajo(motor, hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}])
    comercio = ComercioFalso([_pagado(t, "padre-1"), _pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_ninos"] == 1


async def test_estados_de_trabajos_del_colegio(motor):
    # Tres estados de negocio del colegio, con y sin pedido pagado: los cuenta
    # todos (no solo los pagados). Un trabajo de otro colegio no cuenta.
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.ESPERA_REVISION.value,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"referencia": "h2", "colegio_id": COLEGIO, "grado": "Cuarto"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.FALLIDO.value,
        hijos=[{"referencia": "h3", "colegio_id": COLEGIO, "grado": "Tercero"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"referencia": "h4", "colegio_id": OTRO_COLEGIO, "grado": "Quinto"}],
    )
    comercio = ComercioFalso([])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["estados_trabajos"] == {
        "espera_revision": 1,
        "publicado": 1,
        "fallido": 1,
    }


async def test_colegio_sin_pedidos_da_vacio(motor):
    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, ComercioFalso([]))
    assert resumen == {
        "colegio_id": COLEGIO,
        "total_padres": 0,
        "total_ninos": 0,
        "por_padre": [],
        "por_grado": [],
        "estados_trabajos": {"espera_revision": 0, "publicado": 0, "fallido": 0},
    }
