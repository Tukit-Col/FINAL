"""El kit de fase 1 muestra tambien lo que no se busca en catalogo."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_FASE1 = Path(__file__).resolve().parent / "fase1.py"
_spec = importlib.util.spec_from_file_location("ensayo_fase1", _FASE1)
assert _spec is not None and _spec.loader is not None
fase1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fase1)


@pytest.mark.asyncio
async def test_el_jardin_aparece_en_el_kit_con_mensaje():
    filas = await fase1.responder(
        [
            (
                "CARPETA IDEAS CREATIVAS, la puede adquirir directamente en el jardin",
                None,
            ),
            (
                "EXPEDICION MATEMATICA. Este texto se debe adquirir directamente con la editorial.",
                None,
            ),
        ]
    )

    assert len(filas) == 2
    jardin, editorial = filas

    assert jardin["busca_en_catalogo"] is False
    assert jardin["tipo_item"] == "util"
    assert jardin["modo_adquisicion"] == "venta_directa_editorial"
    assert jardin["mensaje"] == ("Se adquiere directamente en el colegio. Tukit no lo incluye en la compra.")
    assert jardin["emparejamiento"] is None

    assert editorial["busca_en_catalogo"] is False
    assert editorial["tipo_item"] == "texto"
    assert editorial["modo_adquisicion"] == "venta_directa_editorial"
    assert editorial["mensaje"] == (
        "Se compra directamente con la editorial. Tukit no lo incluye en la compra."
    )
    assert editorial["emparejamiento"] is None
