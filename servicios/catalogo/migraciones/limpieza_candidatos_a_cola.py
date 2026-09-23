"""Limpieza puntual: saca del catalogo lo que la maquina metio sin revisar.

La version vieja de `completar` insertaba sus sugerencias directo en
`producto_canonico` (calidad 0,4, `curado_por = AGENTE_FIRECRAWL`). El efecto
era el que el quinto filtro no atrapa: una poinsettia figuraba como lentejuela y
un lavaloza como esponja DENTRO del catalogo que ve el papa. La version nueva de
`completar` las encola en `propuesta_producto` para que una persona apruebe o
descarte; este script arregla la base viva que quedo sucia de las corridas
viejas.

Que hace, en una sola transaccion:

  1. Copia cada producto de maquina (con su unica oferta y su ultimo precio) a la
     cola `propuesta_producto` como candidato 'pendiente'.
  2. Lo borra del catalogo. El ON DELETE CASCADE de `oferta_tienda` y
     `precio_oferta` se lleva su oferta y su precio.

No toca los libros (`TK-LIB-*`): son legitimos y se re-sintetizan en cada carga.

Es idempotente por dos vias que se refuerzan: el id de cada propuesta se deriva
del contenido (mismo `_uuid_estable` que el resto del catalogo), y el INSERT usa
la llave natural (tienda, referencia_externa). Una segunda corrida ya no
encuentra productos de maquina que migrar.

El camino reproducible ya NO produce esto: un `bd-cargar` limpio (que no trae
filas de maquina) mas el `bd-completar` nuevo (que encola en vez de insertar)
nunca deja una sugerencia como producto. Por eso esto es limpieza de datos de
una vez, no un paso del pipeline.

Uso:

    make bd-limpiar-candidatos            # aplica
    make bd-limpiar-candidatos ARGS=--ensayo   # cuenta sin tocar nada
"""

from __future__ import annotations

import argparse
import asyncio

from tukit_catalogo.cargador import AGENTE_FIRECRAWL, _uuid_estable


async def _principal(ensayo: bool) -> int:
    from sqlalchemy import delete, select
    from sqlalchemy.dialects.postgresql import insert
    from tukit_catalogo.modelos import Base
    from tukit_comun.bd import crear_motor

    producto = Base.metadata.tables["producto_canonico"]
    oferta = Base.metadata.tables["oferta_tienda"]
    precio = Base.metadata.tables["precio_oferta"]
    concepto = Base.metadata.tables["concepto"]
    propuesta = Base.metadata.tables["propuesta_producto"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            # Cada producto de maquina con su unica oferta, su ultimo precio y el
            # nombre del concepto (que hara de texto_origen en la cola).
            filas = list(
                await conexion.execute(
                    select(
                        producto.c.id,
                        producto.c.concepto_id,
                        producto.c.nombre,
                        producto.c.marca,
                        producto.c.ean,
                        producto.c.imagen_url,
                        producto.c.nivel,
                        oferta.c.tienda_id,
                        oferta.c.referencia_externa,
                        oferta.c.url,
                        oferta.c.disponible,
                        concepto.c.nombre_canonico,
                        precio.c.valor_centavos,
                    )
                    .select_from(
                        producto.join(oferta, oferta.c.producto_canonico_id == producto.c.id)
                        .join(concepto, concepto.c.id == producto.c.concepto_id)
                        .join(precio, precio.c.oferta_id == oferta.c.id)
                    )
                    .where(
                        producto.c.curado_por == AGENTE_FIRECRAWL,
                        producto.c.sku_interno.notlike("TK-LIB-%"),
                        precio.c.valor_centavos > 0,
                    )
                )
            )

            candidatos = [
                {
                    "id": _uuid_estable("migracion", "cola", str(f.tienda_id), f.referencia_externa),
                    "concepto_id": f.concepto_id,
                    "concepto_sugerido": None,
                    "texto_origen": f.nombre_canonico or f.nombre[:512],
                    "version_lista_id": None,
                    "item_lista_id": None,
                    "origen": "scraper",
                    "tienda_id": f.tienda_id,
                    "referencia_externa": f.referencia_externa,
                    "url": f.url,
                    "nombre": f.nombre[:512],
                    "marca": f.marca,
                    "ean": f.ean,
                    "imagen_url": f.imagen_url,
                    "precio_centavos": f.valor_centavos,
                    "disponible": True if f.disponible is None else f.disponible,
                    "especificaciones": {},
                    "nivel_sugerido": f.nivel,
                    "puntaje": 0.4,
                    "estado": "pendiente",
                }
                for f in filas
            ]

            print(f"Productos de maquina a mover a la cola: {len(candidatos)}")
            if ensayo:
                print("(--ensayo: no se escribio nada)")
                return 0

            encoladas = 0
            if candidatos:
                resultado = await conexion.execute(
                    insert(propuesta)
                    .values(candidatos)
                    .on_conflict_do_nothing(constraint="uq_propuesta_referencia")
                )
                encoladas = resultado.rowcount or 0

            borrados = (
                await conexion.execute(
                    delete(producto).where(
                        producto.c.curado_por == AGENTE_FIRECRAWL,
                        producto.c.sku_interno.notlike("TK-LIB-%"),
                    )
                )
            ).rowcount
    finally:
        await motor.cerrar()

    print(f"Encolados {encoladas} candidatos, borrados {borrados} productos de maquina del catalogo.")
    print("Revisalos con  python -m tukit_catalogo.descubrir --pendientes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mueve las sugerencias de maquina del catalogo a la cola.")
    parser.add_argument("--ensayo", action="store_true", help="cuenta sin escribir")
    return asyncio.run(_principal(parser.parse_args().ensayo))


if __name__ == "__main__":
    raise SystemExit(main())
