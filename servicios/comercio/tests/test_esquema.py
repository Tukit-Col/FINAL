"""El esquema tiene las 17 tablas que el manifiesto le declara a Comercio.

Un conteo, no una lista de nombres: si falta o sobra una tabla respecto a lo
declarado, el numero lo delata sin tener que mantener dos listas en paralelo.
"""

from __future__ import annotations

from tukit_comercio.modelos import Base

TABLAS_ESPERADAS = {
    "pedido",
    "linea_pedido",
    "devolucion",
    "zona_entrega",
    "ruta_reparto",
    "envio",
    "inventario",
    "reserva_inventario",
    "pago",
    "evento_pasarela_procesado",
    "proveedor",
    "condicion_comercial",
    "precio_proveedor",
    "inventario_proveedor",
    "pedido_mayorista",
    "item_pedido_mayorista",
    "bandeja_salida",
}


def test_numero_de_tablas():
    assert len(Base.metadata.tables) == 17


def test_tablas_coinciden_con_el_manifiesto():
    assert set(Base.metadata.tables) == TABLAS_ESPERADAS
