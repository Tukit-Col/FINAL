"""Saca empaque, atributos e imagenes de lo que ya se sabe de cada producto.

Decisiones:
- El empaque y los atributos ya estan escritos en el nombre del producto; hay que leerlos bien, no
  salir a la red. La imagen sale de la ficha cuya direccion guarda `oferta_tienda.url`.
- Un `xN` cuenta empaques salvo que lo siga una unidad de medida ("Tempera de 12 ml x 12 unidades"
  tiene dos doces y solo el segundo multiplica), porque `unidades_a_comprar` es
  techo(cantidad pedida / unidades por empaque).
- Las reglas puras viven en `extraccion.py`; aqui solo se orquesta el lote.

Uso:  python -m tukit_catalogo.enriquecer [--solo-validar] [--imagenes]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import tiendas
from .embeddings import Embeder, texto_de_producto
from .extraccion import Empaque, atributos_de_ficha, extraer_atributos, extraer_empaque, extraer_personaje


def imagen_desde_ficha(url_oferta: str) -> str | None:
    encontrada = tiendas.ficha(url_oferta)
    return encontrada.imagen_url if encontrada else None


def embeddings_a_actualizar(productos: list[dict[str, Any]], embeder: Embeder) -> list[dict[str, Any]]:
    modelo = getattr(embeder, "modelo", None) or getattr(embeder, "__name__", "embeder")
    pendientes: list[tuple[dict[str, Any], str]] = []
    for p in productos:
        texto = texto_de_producto(p.get("nombre", ""), p.get("concepto"), p.get("atributos"))
        vigente = p.get("texto_embedding") == texto and p.get("embedding_model") == modelo
        if not vigente:
            pendientes.append((p, texto))

    if not pendientes:
        return []

    vectores = embeder([texto for _, texto in pendientes])
    return [
        {
            "pid": p["id"],
            "embedding": vector,
            "embedding_model": modelo,
            "texto_embedding": texto,
        }
        for (p, texto), vector in zip(pendientes, vectores, strict=True)
    ]


async def _cargar_contexto() -> tuple[
    list[dict[str, Any]], dict[str, tuple[str, ...]], dict[str, list[str]], dict[str, str], dict[str, str]
]:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    concepto = Base.metadata.tables["concepto"]
    oferta = Base.metadata.tables["oferta_tienda"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            productos = [
                dict(f._mapping)
                for f in await conexion.execute(
                    select(
                        producto.c.id,
                        producto.c.nombre,
                        producto.c.concepto_id,
                        producto.c.imagen_url,
                        producto.c.unidades_por_empaque,
                        producto.c.unidad_base,
                        producto.c.atributos,
                        producto.c.personaje,
                        producto.c.texto_embedding,
                        producto.c.embedding_model,
                    )
                )
            ]
            requeridos: dict[str, tuple[str, ...]] = {}
            nombres_concepto: dict[str, str] = {}
            codigos_concepto: dict[str, str] = {}
            for f in await conexion.execute(
                select(
                    concepto.c.id,
                    concepto.c.codigo,
                    concepto.c.nombre_canonico,
                    concepto.c.atributos_discriminantes,
                    concepto.c.atributos_descriptivos,
                )
            ):
                requeridos[str(f.id)] = tuple(f.atributos_discriminantes or ()) + tuple(
                    f.atributos_descriptivos or ()
                )
                nombres_concepto[str(f.id)] = f.nombre_canonico
                codigos_concepto[str(f.id)] = f.codigo
            urls: dict[str, list[str]] = {}
            for f in await conexion.execute(
                select(oferta.c.producto_canonico_id, oferta.c.url).where(oferta.c.url.is_not(None))
            ):
                urls.setdefault(str(f.producto_canonico_id), []).append(f.url)
    finally:
        await motor.cerrar()
    return productos, requeridos, urls, nombres_concepto, codigos_concepto


async def _guardar_embeddings(cambios: list[dict[str, Any]]) -> None:
    if not cambios:
        return
    from sqlalchemy import bindparam, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            sentencia = (
                update(producto)
                .where(producto.c.id == bindparam("pid"))
                .values(
                    embedding=bindparam("embedding"),
                    embedding_model=bindparam("embedding_model"),
                    texto_embedding=bindparam("texto_embedding"),
                )
            )
            await conexion.execute(sentencia, cambios)
    finally:
        await motor.cerrar()


async def _guardar(cambios: list[dict[str, Any]]) -> None:
    from sqlalchemy import bindparam, select, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            sentencia = (
                update(producto)
                .where(producto.c.id == bindparam("pid"))
                .values(
                    unidades_por_empaque=bindparam("unidades_por_empaque"),
                    unidad_base=bindparam("unidad_base"),
                    atributos=bindparam("atributos"),
                    imagen_url=bindparam("imagen_url"),
                    personaje=bindparam("personaje"),
                )
            )
            await conexion.execute(sentencia, cambios)

            concepto = Base.metadata.tables["concepto"]
            await conexion.execute(
                update(concepto)
                .where(
                    concepto.c.id.in_(select(producto.c.concepto_id).where(producto.c.personaje.is_not(None)))
                )
                .values(admite_personaje=True)
            )
    finally:
        await motor.cerrar()


def empaque_combinado(unidades_guardadas: int | None, unidad_guardada: str | None, leido: Empaque) -> Empaque:
    if unidades_guardadas and unidades_guardadas > 1:
        return Empaque(unidades_guardadas, unidad_guardada or leido.unidad_base)
    return leido


def atributos_combinados(
    guardados: dict[str, Any], leidos: dict[str, Any], reextraer: frozenset[str] = frozenset()
) -> dict[str, Any]:
    conservados = {k: v for k, v in guardados.items() if k not in reextraer}
    return {**leidos, **conservados}


def _leer_reextraer(pedidos: list[str]) -> dict[str, frozenset[str]]:
    salida: dict[str, set[str]] = {}
    for pedido in pedidos:
        codigo, _, claves = pedido.partition(":")
        if not codigo or not claves:
            raise SystemExit(f"--reextraer espera CONCEPTO:clave[,clave], no {pedido!r}")
        salida.setdefault(codigo.strip(), set()).update(c.strip() for c in claves.split(",") if c.strip())
    return {c: frozenset(v) for c, v in salida.items()}


async def _principal(
    con_imagenes: bool,
    solo_validar: bool,
    con_embeddings: bool = True,
    reextraer: dict[str, frozenset[str]] | None = None,
    informe: str | None = None,
    con_fichas: bool = False,
) -> int:
    productos, requeridos, urls, nombres_concepto, codigos = await _cargar_contexto()
    reextraer = reextraer or {}

    imagenes: dict[str, str] = {}
    de_ficha: dict[str, dict[str, Any]] = {}
    if con_imagenes or con_fichas:

        def le_falta_algo(p: dict[str, Any]) -> bool:
            if con_imagenes and (not p["imagen_url"] or not p["atributos"]):
                return True
            guardados = p["atributos"] or {}
            return con_fichas and any(a not in guardados for a in requeridos.get(str(p["concepto_id"]), ()))

        pendientes = [(p, urls.get(str(p["id"]), [])) for p in productos if le_falta_algo(p)]
        pendientes = [(p, u) for p, u in pendientes if u]
        print(f"Leyendo la ficha de {len(pendientes)} productos en las tiendas que ya se conocian...")

        def resolver(par):
            producto, direcciones = par
            for direccion in direcciones:
                encontrada = tiendas.ficha(direccion)
                if encontrada:
                    return str(producto["id"]), encontrada
            return str(producto["id"]), None

        leidas = 0
        with ThreadPoolExecutor(max_workers=6) as grupo:
            for pid, oferta in grupo.map(resolver, pendientes):
                if oferta is None:
                    continue
                leidas += 1
                if oferta.imagen_url:
                    imagenes[pid] = oferta.imagen_url
                de_ficha[pid] = {
                    "especificaciones": oferta.especificaciones,
                    "personaje": oferta.especificaciones.get("Personaje"),
                }
        print(f"  fichas leidas: {leidas}/{len(pendientes)}   con portada: {len(imagenes)}")

    cambios = []
    empaques_nuevos = atributos_nuevos = 0
    for p in productos:
        attrs_concepto = requeridos.get(str(p["concepto_id"]), ())
        empaque = extraer_empaque(p["nombre"], attrs_concepto)
        attrs = extraer_atributos(p["nombre"], attrs_concepto)

        ficha_p = de_ficha.get(str(p["id"]))
        if ficha_p:
            attrs = {**atributos_de_ficha(ficha_p["especificaciones"], attrs_concepto), **attrs}

        empaque = empaque_combinado(p["unidades_por_empaque"], p.get("unidad_base"), empaque)
        if empaque.unidades != p["unidades_por_empaque"]:
            empaques_nuevos += 1
        if attrs and not p["atributos"]:
            atributos_nuevos += 1

        cambios.append(
            {
                "pid": p["id"],
                "unidades_por_empaque": empaque.unidades,
                "unidad_base": empaque.unidad_base,
                "atributos": atributos_combinados(
                    p["atributos"] or {},
                    attrs,
                    reextraer.get(codigos.get(str(p["concepto_id"]), ""), frozenset()),
                ),
                "imagen_url": p["imagen_url"] or imagenes.get(str(p["id"])),
                "personaje": (
                    p["personaje"] or extraer_personaje(p["nombre"]) or (ficha_p or {}).get("personaje")
                ),
            }
        )

    if informe:
        _escribir_informe(informe, productos, cambios, codigos)

    con_personaje = sum(1 for c in cambios if c["personaje"])
    con_attrs = sum(1 for c in cambios if c["atributos"])
    con_img = sum(1 for c in cambios if c["imagen_url"])
    total = len(cambios)
    print("\n=== lo que se puede leer del nombre ===")
    print(f"  empaque corregido (ya no es 1)     {empaques_nuevos:5}/{total}")
    print(f"  productos con atributos            {con_attrs:5}/{total}")
    print(f"     nuevos en esta pasada           {atributos_nuevos:5}")
    print(f"  productos con imagen               {con_img:5}/{total}")
    print(f"  productos con personaje            {con_personaje:5}/{total}")

    plan_embeddings: list[dict[str, Any]] = []
    if con_embeddings:
        embeder = _embeder_por_entorno()
        if embeder is None:
            print("\n(sin GEMINI_API_KEY: no se calculan embeddings)")
        else:
            por_pid = {str(c["pid"]): c for c in cambios}
            para_embeber = [
                {
                    "id": p["id"],
                    "nombre": p["nombre"],
                    "concepto": nombres_concepto.get(str(p["concepto_id"])),
                    "atributos": por_pid[str(p["id"])]["atributos"],
                    "texto_embedding": p.get("texto_embedding"),
                    "embedding_model": p.get("embedding_model"),
                }
                for p in productos
            ]
            plan_embeddings = embeddings_a_actualizar(para_embeber, embeder)
            print(f"  embeddings a (re)calcular          {len(plan_embeddings):5}/{total}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    await _guardar(cambios)
    await _guardar_embeddings(plan_embeddings)
    print("\nEscrito.")
    return 0


def _escribir_informe(
    ruta: str, productos: list[dict[str, Any]], cambios: list[dict[str, Any]], codigos: dict[str, str]
) -> None:
    import csv

    por_pid = {str(c["pid"]): c for c in cambios}
    filas = 0
    with open(ruta, "w", encoding="utf-8", newline="") as salida:
        escritor = csv.writer(salida)
        escritor.writerow(["concepto", "producto_id", "nombre", "atributo", "antes", "despues"])
        for p in productos:
            antes = p["atributos"] or {}
            despues = por_pid[str(p["id"])]["atributos"]
            for clave in sorted(set(antes) | set(despues)):
                if antes.get(clave) != despues.get(clave):
                    escritor.writerow(
                        [
                            codigos.get(str(p["concepto_id"]), ""),
                            p["id"],
                            p["nombre"],
                            clave,
                            antes.get(clave, ""),
                            despues.get(clave, ""),
                        ]
                    )
                    filas += 1
    print(f"  informe: {filas} cambios de atributo en {ruta}")


def _embeder_por_entorno() -> Embeder | None:
    import os

    from .embeddings import embeder_gemini

    return embeder_gemini if os.environ.get("GEMINI_API_KEY", "").strip() else None


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--imagenes", action="store_true", help="ir a la red por las portadas")
    analizador.add_argument("--sin-embeddings", action="store_true", help="no calcular el canal semantico")
    analizador.add_argument("--solo-validar", action="store_true")
    analizador.add_argument(
        "--reextraer",
        action="append",
        default=[],
        metavar="CONCEPTO:clave[,clave]",
        help="releer del nombre estas claves aunque ya esten guardadas (p. ej. C006:tipo,punta)",
    )
    analizador.add_argument("--informe", metavar="RUTA.csv", help="escribir cada cambio de atributo a un CSV")
    analizador.add_argument(
        "--fichas",
        action="store_true",
        help="leer la ficha de la tienda de los productos a los que les falta un atributo (va a la red)",
    )
    args = analizador.parse_args()
    return asyncio.run(
        _principal(
            args.imagenes,
            args.solo_validar,
            not args.sin_embeddings,
            reextraer=_leer_reextraer(args.reextraer),
            informe=args.informe,
            con_fichas=args.fichas,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
