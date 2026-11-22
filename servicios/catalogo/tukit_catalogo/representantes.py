from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

_ELEGIDOS = """
WITH precio AS (
  SELECT o.producto_canonico_id AS pid, min(pr.valor_centavos) AS c
  FROM oferta_tienda o JOIN precio_oferta pr ON pr.oferta_id = o.id
  WHERE o.activo AND pr.vigente_hasta IS NULL GROUP BY 1),
utiles AS (
  SELECT p.id, p.concepto_id, p.nivel, coalesce(p.personaje, '') AS pj, p.sku_interno, precio.c
  FROM producto_canonico p JOIN concepto c ON c.id = p.concepto_id LEFT JOIN precio ON precio.pid = p.id
  WHERE p.activo AND c.tipo_item <> 'libro_libre' AND c.categoria NOT ILIKE '%libro%'),
elegido AS (
  SELECT DISTINCT ON (concepto_id, nivel, pj) id FROM utiles
  ORDER BY concepto_id, nivel, pj, (sku_interno ~ '^TK-C[0-9]{3}-') DESC, c NULLS LAST, sku_interno)
"""

_CAMBIOS = (
    _ELEGIDOS
    + """
SELECT count(*) FROM producto_canonico p
WHERE p.id IN (SELECT id FROM utiles)
  AND p.es_representante_canonico <> (p.id IN (SELECT id FROM elegido))
"""
)

_ESCRIBIR = (
    _ELEGIDOS
    + """
UPDATE producto_canonico p SET es_representante_canonico = (p.id IN (SELECT id FROM elegido))
WHERE p.id IN (SELECT id FROM utiles)
  AND p.es_representante_canonico <> (p.id IN (SELECT id FROM elegido))
"""
)


async def _principal(escribir: bool) -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            cambios = (await conexion.execute(text(_CAMBIOS))).scalar_one()
            if escribir and cambios:
                await conexion.execute(text(_ESCRIBIR))
    finally:
        await motor.cerrar()
    verbo = "corregidos" if escribir else "por corregir (ensayo; usa --escribir)"
    print(f"representantes {verbo}: {cambios}")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--escribir", action="store_true")
    return asyncio.run(_principal(analizador.parse_args().escribir))


if __name__ == "__main__":
    sys.exit(main())
