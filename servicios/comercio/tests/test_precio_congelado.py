"""El precio de una linea queda congelado (ADR 0012, R-PRECIO).

La linea guarda su propio `precio_unitario`; no hay ninguna llave hacia el
precio de Catalogo, asi que un cambio alla no la puede mover. Esta prueba lo
comprueba a nivel de dato: escrito el precio, se lee identico aunque otra linea
del mismo producto lleve otro.
"""

from __future__ import annotations

import pytest
from conftest import agregar_linea, crear_pedido

pytestmark = pytest.mark.asyncio


async def test_precio_de_linea_se_conserva(db):
    pedido = await crear_pedido(db)
    linea = await agregar_linea(db, pedido, precio=4500, cantidad=3)
    await db.refresh(linea)
    assert linea.precio_unitario == 4500
    assert linea.cantidad == 3


async def test_dos_lineas_mismo_producto_precios_independientes(db):
    pedido = await crear_pedido(db)
    a = await agregar_linea(db, pedido, precio=4500)
    b = await agregar_linea(db, pedido, precio=5200)
    await db.refresh(a)
    await db.refresh(b)
    # El precio vive en la linea: dos renglones pueden diferir aunque el
    # catalogo tenga un solo precio publico hoy.
    assert a.precio_unitario == 4500
    assert b.precio_unitario == 5200
