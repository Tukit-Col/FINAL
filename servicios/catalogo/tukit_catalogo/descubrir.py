"""Da de alta lo que una lista nueva pide y el catalogo todavia no tiene.

Decisiones:
- El catalogo es propio y curado, y crece como una cache progresiva: el emparejamiento de un
  acudiente corre siempre contra la base propia y una tienda solo interviene cuando entra la lista
  de un colegio que nadie ha revisado y un renglon no encuentra nada.
- Las listas ya revisadas nunca consultan tiendas: `version_lista_oficial.revisada_en` las cierra
  y no se reabren. El codigo que sale a una tienda solo es alcanzable desde una version sin
  revisar.
- Escribe propuestas, nunca productos: una busqueda por texto trae resultados absurdos (para
  "punzon punta metalica", correctores de punta fina), asi que decide una persona.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import tiendas
from .cargador import AGENTE_FIRECRAWL, _uuid_estable, ean13, isbn13_valido, normalizar_isbn
from .clasificacion import _plano, clasificar, consulta_desde_renglon
from .extraccion import Empaque, atributos_de_ficha, extraer_atributos, extraer_empaque, extraer_personaje

PRECIO_MINIMO = 1000
PRECIO_MAXIMO = 400_000


def _ean_valido(ean: str | None) -> str | None:
    ean = (ean or "").strip()
    return ean if ean.isdigit() and len(ean) in (8, 12, 13) else None


@dataclass(frozen=True)
class Propuesta:
    concepto_id: uuid.UUID | None
    concepto_sugerido: str | None
    texto_origen: str
    oferta: tiendas.Oferta


def buscar_candidatos(consulta: str, ancla: str = "", cuantos: int = 3) -> list[tiendas.Oferta]:
    encontrados: list[tiendas.Oferta] = []
    for tienda in tiendas.DOMINIOS:
        encontrados += [
            o
            for o in tiendas.buscar(tienda, consulta)
            if o.disponible and o.imagen_url and PRECIO_MINIMO <= o.precio_cop <= PRECIO_MAXIMO
        ]

    raiz = _plano(ancla or consulta).split()
    if raiz:
        prefijo = raiz[0][:5]
        encontrados = [o for o in encontrados if prefijo in _plano(o.nombre)]

    if not encontrados:
        return []

    ordenados = sorted(encontrados, key=lambda o: o.precio_cop)
    if len(ordenados) <= cuantos:
        return ordenados
    posiciones = [len(ordenados) // 6, len(ordenados) // 2, (5 * len(ordenados)) // 6]
    vistos, salida = set(), []
    for posicion in posiciones:
        elegido = ordenados[min(posicion, len(ordenados) - 1)]
        if elegido.sku not in vistos:
            vistos.add(elegido.sku)
            salida.append(elegido)
    return salida


NIVEL_POR_POSICION = ("economico", "confiable", "premium")


async def _contexto():
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    tienda = Base.metadata.tables["tienda"]
    propuesta = Base.metadata.tables["propuesta_producto"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            conceptos = [
                {
                    "id": f.id,
                    "codigo": f.codigo,
                    "nombre": f.nombre_canonico,
                    "sinonimos": list(f.sinonimos or ()),
                    "attrs": tuple(f.atributos_discriminantes or ()) + tuple(f.atributos_descriptivos or ()),
                }
                for f in await conexion.execute(
                    select(
                        concepto.c.id,
                        concepto.c.codigo,
                        concepto.c.nombre_canonico,
                        concepto.c.sinonimos,
                        concepto.c.atributos_discriminantes,
                        concepto.c.atributos_descriptivos,
                    ).where(concepto.c.activo)
                )
            ]
            slugs = {f.slug: f.id for f in await conexion.execute(select(tienda.c.slug, tienda.c.id))}
            producto = Base.metadata.tables["producto_canonico"]
            cobertura: dict[str, set[str]] = {}
            for f in await conexion.execute(
                select(producto.c.concepto_id, producto.c.nivel).where(producto.c.activo)
            ):
                cobertura.setdefault(str(f.concepto_id), set()).add(f.nivel)
            decididos = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(select(propuesta.c.tienda_id, propuesta.c.referencia_externa))
            }
            ofertados = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(
                    select(
                        Base.metadata.tables["oferta_tienda"].c.tienda_id,
                        Base.metadata.tables["oferta_tienda"].c.referencia_externa,
                    )
                )
            }
    finally:
        await motor.cerrar()
    return conceptos, slugs, decididos | ofertados, cobertura


ATRIBUTOS_VERIFICADOS = "atributos_verificados"
EMPAQUE_VERIFICADO = "unidades_por_empaque_verificado"


def atributos_verificados(especificaciones: dict[str, Any]) -> dict[str, Any]:
    crudo = especificaciones.get(ATRIBUTOS_VERIFICADOS)
    if not crudo:
        return {}
    try:
        valor = json.loads(crudo) if isinstance(crudo, str) else crudo
    except ValueError:
        return {}
    return dict(valor) if isinstance(valor, dict) else {}


def atributos_al_aprobar(
    nombre: str, especificaciones: dict[str, Any], attrs_concepto: tuple[str, ...]
) -> dict[str, Any]:
    return {
        **atributos_de_ficha(especificaciones, attrs_concepto),
        **extraer_atributos(nombre, attrs_concepto),
        **atributos_verificados(especificaciones),
    }


async def _encolar(propuestas: list[dict[str, Any]]) -> int:
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    if not propuestas:
        return 0
    tabla = Base.metadata.tables["propuesta_producto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            resultado = await conexion.execute(
                insert(tabla).values(propuestas).on_conflict_do_nothing(constraint="uq_propuesta_referencia")
            )
            return resultado.rowcount or 0
    finally:
        await motor.cerrar()


class PuertaCerrada(Exception):
    pass


def exigir_sin_revisar(id_corto: str, existe: bool, revisada_en: datetime | None) -> None:
    if not existe:
        raise PuertaCerrada(f"No existe ninguna version de lista que empiece por {id_corto}")
    if revisada_en is not None:
        raise PuertaCerrada(
            f"Esa lista ya fue revisada el {revisada_en:%Y-%m-%d}. "
            "Una lista revisada se responde con el catalogo y no consulta tiendas."
        )


@dataclass(frozen=True)
class Revision:
    version_id: uuid.UUID
    colegio: str
    grado: str
    anio: int
    items: tuple[tuple[uuid.UUID, str], ...]


async def abrir_revision(id_corto: str) -> Revision:
    from sqlalchemy import Text, cast, select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    lista = Base.metadata.tables["lista_oficial"]
    item = Base.metadata.tables["item_lista_oficial"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                    )
                    .select_from(version.join(lista, lista.c.id == version.c.lista_id))
                    .where(cast(version.c.id, Text).like(f"{id_corto}%"))
                )
            ).first()
            exigir_sin_revisar(id_corto, fila is not None, fila.revisada_en if fila else None)
            assert fila is not None
            renglones = tuple(
                (f.id, f.texto_original)
                for f in await conexion.execute(
                    select(item.c.id, item.c.texto_original)
                    .where(item.c.version_id == fila.id)
                    .order_by(item.c.orden)
                )
            )
    finally:
        await motor.cerrar()

    return Revision(
        version_id=fila.id,
        colegio=str(fila.colegio_id)[:8],
        grado=fila.grado,
        anio=fila.anio_lectivo,
        items=renglones,
    )


async def proponer(revision: Revision) -> None:
    conceptos, slugs, ya_decididos, cobertura = await _contexto()
    renglones = [texto for _, texto in revision.items]
    ids_item = {texto: iid for iid, texto in revision.items}
    print(f"Revision de {revision.colegio} {revision.grado} {revision.anio}")
    print(f"Renglones a resolver: {len(renglones)}\n")

    propuestas: list[dict[str, Any]] = []
    en_casa = fuera = 0
    for renglon in renglones:
        concepto_id, nombre_concepto, parecido = clasificar(renglon, conceptos)
        consulta = consulta_desde_renglon(renglon)

        if parecido < 0.5:
            print(f"  {renglon[:44]:46} -> CONCEPTO NUEVO: {consulta}")
            concepto_id, sugerido = None, consulta[:128]
        else:
            concepto_id, sugerido = concepto_id, None
            nuestros = cobertura.get(str(concepto_id), set())
            if len(nuestros) >= 3:
                en_casa += 1
                print(f"  {renglon[:44]:46} -> {nombre_concepto}: YA LO TENEMOS")
                print(f"     {len(nuestros)} niveles en catalogo, no se consulta ninguna tienda")
                continue
            faltan = {"economico", "confiable", "premium"} - nuestros
            print(f"  {renglon[:44]:46} -> {nombre_concepto} ({parecido:.0%})")
            print(f"     lo tenemos a medias: falta {', '.join(sorted(faltan))}")

        fuera += 1
        candidatos = buscar_candidatos(consulta, ancla=nombre_concepto if concepto_id else consulta)
        nuevos = [c for c in candidatos if (str(slugs.get(c.tienda)), c.sku) not in ya_decididos]
        print(f"     se consulta la tienda: {len(candidatos)} candidatos, {len(nuevos)} sin decidir")

        for posicion, oferta in enumerate(nuevos):
            print(f"       ${oferta.precio_cop:>7}  {oferta.tienda:13} {oferta.nombre[:46]}")
            propuestas.append(
                {
                    "id": _uuid_estable("propuesta", oferta.tienda, oferta.sku),
                    "concepto_id": concepto_id,
                    "concepto_sugerido": sugerido,
                    "texto_origen": renglon,
                    "tienda_id": slugs[oferta.tienda],
                    "referencia_externa": oferta.sku,
                    "url": oferta.url or None,
                    "nombre": oferta.nombre[:512],
                    "marca": oferta.marca,
                    "ean": oferta.ean,
                    "imagen_url": oferta.imagen_url,
                    "precio_centavos": oferta.precio_cop * 100,
                    "disponible": oferta.disponible,
                    "especificaciones": oferta.especificaciones,
                    "nivel_sugerido": NIVEL_POR_POSICION[min(posicion, 2)],
                    "puntaje": round(min(parecido, 0.9), 3) if concepto_id else 0.3,
                    "estado": "pendiente",
                    "origen": "scraper",
                    "version_lista_id": revision.version_id,
                    "item_lista_id": ids_item.get(renglon),
                }
            )

    encoladas = await _encolar(propuestas)
    print(f"\n  resueltos con nuestro catalogo, sin salir  {en_casa}/{len(renglones)}")
    print(f"  hubo que consultar una tienda              {fuera}/{len(renglones)}")
    print(f"\nEncoladas para revision: {encoladas}")
    print("Revisalas con  --pendientes  y resuelvelas con  --aprobar / --rechazar")
    print(f"Cuando no quede nada pendiente:  --cerrar {str(revision.version_id)[:8]}")


async def listar_pendientes() -> None:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    propuesta = Base.metadata.tables["propuesta_producto"]
    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    select(
                        propuesta.c.id,
                        propuesta.c.texto_origen,
                        propuesta.c.nombre,
                        propuesta.c.precio_centavos,
                        propuesta.c.nivel_sugerido,
                        propuesta.c.concepto_sugerido,
                        concepto.c.nombre_canonico,
                    )
                    .select_from(propuesta.outerjoin(concepto, concepto.c.id == propuesta.c.concepto_id))
                    .where(propuesta.c.estado == "pendiente")
                    .order_by(propuesta.c.propuesta_en)
                )
            ).all()
    finally:
        await motor.cerrar()

    if not filas:
        print("No hay nada pendiente de revisar.")
        return
    print(f"{len(filas)} propuestas pendientes\n")
    for f in filas:
        destino = f.nombre_canonico or f"nuevo: {f.concepto_sugerido}"
        print(f"  {str(f.id)[:8]}  {destino[:22]:24} <- pedido: {f.texto_origen[:30]}")
        print(f"            ${f.precio_centavos // 100:>7} {f.nivel_sugerido or '-':10} {f.nombre[:52]}")


async def resolver(
    id_corto: str,
    aprobar: bool,
    nivel: str | None,
    motivo: str | None,
    no_surtir: bool = False,
    overrides: dict[str, Any] | None = None,
) -> int:
    from sqlalchemy import Text, cast, func, select, update
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    propuesta = Base.metadata.tables["propuesta_producto"]
    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(propuesta).where(cast(propuesta.c.id, Text).like(f"{id_corto}%"))
                )
            ).first()
            if fila is None:
                print(f"No encuentro ninguna propuesta que empiece por {id_corto}")
                return 1
            if fila.estado != "pendiente":
                print(f"Esa propuesta ya esta {fila.estado}.")
                return 1

            if not aprobar:
                await conexion.execute(
                    update(propuesta)
                    .where(propuesta.c.id == fila.id)
                    .values(estado="rechazada", motivo=motivo, resuelta_en=datetime.now(UTC))
                )
                print(f"Rechazada: {fila.nombre[:50]}")
                if motivo:
                    print(f"  motivo: {motivo}")
                if no_surtir:
                    if fila.concepto_id is None:
                        print("  (no se marco no_comprar: la propuesta no tiene concepto asociado)")
                    else:
                        await conexion.execute(
                            update(concepto)
                            .where(concepto.c.id == fila.concepto_id)
                            .values(tipo_item="no_comprar")
                        )
                        print("  concepto marcado 'no_comprar': no se lo ofrecemos al papa.")
                return 0

            if fila.concepto_id is None:
                print("Esta propuesta no tiene concepto. Primero hay que crear el concepto")
                print(f"  sugerido: {fila.concepto_sugerido}")
                return 1

            attrs_concepto = (
                await conexion.execute(
                    select(
                        Base.metadata.tables["concepto"].c.atributos_discriminantes,
                        Base.metadata.tables["concepto"].c.atributos_descriptivos,
                    ).where(Base.metadata.tables["concepto"].c.id == fila.concepto_id)
                )
            ).one()
            attrs_concepto = tuple(attrs_concepto[0] or ()) + tuple(attrs_concepto[1] or ())

            especificaciones = dict(fila.especificaciones or {})
            empaque = extraer_empaque(fila.nombre, attrs_concepto)
            atributos = atributos_al_aprobar(fila.nombre, especificaciones, attrs_concepto)
            if especificaciones.get(EMPAQUE_VERIFICADO, "").isdigit():
                empaque = Empaque(int(especificaciones[EMPAQUE_VERIFICADO]), empaque.unidad_base)

            ov = overrides or {}
            nombre_final = str(ov["nombre"]).strip() if ov.get("nombre") else fila.nombre
            marca_final = ov.get("marca", fila.marca)
            imagen_final = ov.get("imagen_url", fila.imagen_url)
            personaje_final = ov.get("personaje", extraer_personaje(fila.nombre))
            atributos_final = ov.get("atributos", atributos)

            pid = _uuid_estable("aprobado", str(fila.tienda_id), fila.referencia_externa)
            nivel_final = nivel or fila.nivel_sugerido or "confiable"
            producto = Base.metadata.tables["producto_canonico"]
            ean_final = ean13(fila.ean)
            existente = (
                await conexion.scalar(select(producto.c.id).where(producto.c.ean == ean_final))
                if ean_final
                else None
            )
            if existente is not None:
                pid = existente
            ya_hay_representante = await conexion.scalar(
                select(func.count())
                .select_from(producto)
                .where(
                    producto.c.concepto_id == fila.concepto_id,
                    producto.c.nivel == nivel_final,
                    producto.c.personaje.is_(None)
                    if personaje_final is None
                    else producto.c.personaje == personaje_final,
                    producto.c.activo.is_(True),
                    producto.c.es_representante_canonico.is_(True),
                )
            )
            await conexion.execute(
                insert(producto)
                .values(
                    id=pid,
                    concepto_id=fila.concepto_id,
                    ean=ean_final,
                    sku_interno=f"TK-REV-{fila.referencia_externa}"[:64],
                    nombre=nombre_final[:255],
                    marca=marca_final,
                    nivel=nivel_final,
                    personaje=personaje_final,
                    imagen_url=imagen_final,
                    unidad_base=empaque.unidad_base,
                    unidades_por_empaque=empaque.unidades,
                    atributos=atributos_final,
                    es_propio=False,
                    es_representante_canonico=not ya_hay_representante,
                    activo=True,
                    quality_score=0.85,
                    curado_por=AGENTE_FIRECRAWL,
                )
                .on_conflict_do_nothing()
            )

            oferta_id = _uuid_estable("aprobado-oferta", str(fila.tienda_id), fila.referencia_externa)
            await conexion.execute(
                insert(Base.metadata.tables["oferta_tienda"])
                .values(
                    id=oferta_id,
                    producto_canonico_id=pid,
                    tienda_id=fila.tienda_id,
                    referencia_externa=fila.referencia_externa,
                    url=fila.url,
                    metodo_vinculacion="ean" if fila.ean else "manual",
                    confianza_vinculacion=0.85,
                    disponible=fila.disponible,
                    activo=True,
                )
                .on_conflict_do_nothing()
            )
            await conexion.execute(
                insert(Base.metadata.tables["precio_oferta"])
                .values(
                    id=_uuid_estable("aprobado-precio", str(fila.tienda_id), fila.referencia_externa),
                    oferta_id=oferta_id,
                    valor_centavos=fila.precio_centavos,
                    moneda="COP",
                    fuente="scraper",
                    vigente_desde=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
            )
            await conexion.execute(
                update(propuesta)
                .where(propuesta.c.id == fila.id)
                .values(
                    estado="aprobada",
                    producto_canonico_id=pid,
                    resuelta_en=datetime.now(UTC),
                )
            )
    finally:
        await motor.cerrar()

    print(f"Aprobada y en catalogo: {fila.nombre[:52]}")
    resumen = f"nivel {nivel or fila.nivel_sugerido}  ${fila.precio_centavos // 100:,}"
    print(f"  {resumen}  empaque x{empaque.unidades}")
    if atributos:
        print(f"  atributos: {atributos}")
    return 0


async def probar(renglones: list[str]) -> None:
    conceptos, _slugs, _decididos, cobertura = await _contexto()
    print(f"Contra nuestro catalogo, sin salir a ninguna tienda: {len(renglones)} renglones\n")
    resueltos = 0
    for renglon in renglones:
        concepto_id, nombre, parecido = clasificar(renglon, conceptos)
        niveles = cobertura.get(str(concepto_id), set()) if concepto_id else set()
        if parecido >= 0.5 and niveles:
            resueltos += 1
            cubre = ", ".join(sorted(niveles))
            print(f"  OK       {renglon[:40]:42} -> {nombre[:20]:22} [{cubre}]")
        elif parecido >= 0.5:
            print(f"  SIN QUE  {renglon[:40]:42} -> {nombre[:20]:22} concepto sin producto")
        else:
            print(f"  NO       {renglon[:40]:42} -> no lo reconocemos")
    print(f"\n  resueltos con catalogo  {resueltos}/{len(renglones)}")
    if resueltos < len(renglones):
        print("  el resto necesita revision de un administrador para darse de alta")


async def listar_listas() -> None:
    from sqlalchemy import func as f_sql
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    lista = Base.metadata.tables["lista_oficial"]
    item = Base.metadata.tables["item_lista_oficial"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    select(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                        f_sql.count(item.c.id).label("renglones"),
                    )
                    .select_from(
                        version.join(lista, lista.c.id == version.c.lista_id).outerjoin(
                            item, item.c.version_id == version.c.id
                        )
                    )
                    .group_by(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                    )
                    .order_by(version.c.revisada_en.is_(None).desc(), lista.c.grado)
                )
            ).all()
    finally:
        await motor.cerrar()

    if not filas:
        print("No hay listas cargadas todavia.")
        return
    sin_revisar = [f for f in filas if f.revisada_en is None]
    print(f"{len(filas)} versiones de lista, {len(sin_revisar)} sin revisar\n")
    for f in filas:
        estado = "SIN REVISAR" if f.revisada_en is None else f"revisada {f.revisada_en:%Y-%m-%d}"
        print(
            f"  {str(f.id)[:8]}  {str(f.colegio_id)[:8]} {f.grado[:14]:16} "
            f"{f.anio_lectivo}  v{f.numero}  {f.renglones:>3} renglones  {estado}"
        )


async def crear_libro(
    id_corto: str,
    isbn: str,
    titulo: str,
    precio_cop: int,
    tienda: str,
    url: str | None,
    imagen: str | None,
    concepto: str | None,
) -> int:
    revision = await abrir_revision(id_corto)

    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    isbn = normalizar_isbn(isbn) or ""
    if not isbn13_valido(isbn):
        print(f"El ISBN '{isbn}' no pasa el digito de control. Revisalo antes de darlo de alta.")
        return 1

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            tabla_tienda = Base.metadata.tables["tienda"]
            tienda_id = (
                await conexion.execute(select(tabla_tienda.c.id).where(tabla_tienda.c.slug == tienda))
            ).scalar_one_or_none()
            if tienda_id is None:
                print(f"No conozco la tienda '{tienda}'.")
                return 1
            concepto_id = None
            if concepto:
                tabla_concepto = Base.metadata.tables["concepto"]
                concepto_id = (
                    await conexion.execute(
                        select(tabla_concepto.c.id).where(tabla_concepto.c.codigo == concepto)
                    )
                ).scalar_one_or_none()
                if concepto_id is None:
                    print(f"No existe el concepto '{concepto}'.")
                    return 1
    finally:
        await motor.cerrar()

    encoladas = await _encolar(
        [
            {
                "id": _uuid_estable("propuesta", tienda, isbn),
                "concepto_id": concepto_id,
                "concepto_sugerido": None if concepto_id else titulo[:128],
                "texto_origen": titulo,
                "tienda_id": tienda_id,
                "referencia_externa": isbn,
                "url": url,
                "nombre": titulo[:512],
                "marca": None,
                "ean": isbn,
                "imagen_url": imagen,
                "precio_centavos": precio_cop * 100,
                "disponible": True,
                "especificaciones": {"isbn": isbn},
                "nivel_sugerido": "confiable",
                "puntaje": 0.9,
                "estado": "pendiente",
                "origen": "manual",
                "version_lista_id": revision.version_id,
                "item_lista_id": None,
            }
        ]
    )
    if not encoladas:
        print(f"Ese ISBN ya estaba propuesto para {tienda}.")
        return 0
    print(f"Encolado a mano: {titulo[:52]}")
    print(f"  ISBN {isbn}  ${precio_cop:,}  {tienda}")
    print("Apruebalo con  --aprobar  cuando lo verifiques.")
    return 0


async def crear_util(
    id_corto: str,
    concepto: str,
    consulta: str,
    elegir: int | None,
) -> int:
    revision = await abrir_revision(id_corto)

    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            tabla_concepto = Base.metadata.tables["concepto"]
            fila_concepto = (
                await conexion.execute(
                    select(tabla_concepto.c.id, tabla_concepto.c.nombre_canonico).where(
                        tabla_concepto.c.codigo == concepto
                    )
                )
            ).first()
            if fila_concepto is None:
                print(f"No existe el concepto '{concepto}'. Mira los codigos con --pendientes o el CSV.")
                return 1
            tabla_tienda = Base.metadata.tables["tienda"]
            slugs = {
                f.slug: f.id for f in await conexion.execute(select(tabla_tienda.c.slug, tabla_tienda.c.id))
            }
    finally:
        await motor.cerrar()

    candidatos: list[tuple[str, Any]] = []
    for slug in ("exito", "panamericana", "grancentral"):
        if slug not in slugs:
            continue
        for oferta in tiendas.buscar(slug, consulta):
            if not tiendas._coincide(oferta.nombre, consulta):
                continue
            if oferta.precio_cop <= 0 or not oferta.disponible:
                continue
            candidatos.append((slug, oferta))

    candidatos.sort(key=lambda par: par[1].precio_cop)

    if not candidatos:
        print(f"Ninguna tienda devolvio algo que contenga '{consulta}'.")
        print("Prueba otra consulta, o da de alta el dato a mano si lo surte un distribuidor fisico.")
        return 0

    if elegir is None:
        print(f"Candidatos para {concepto} ({fila_concepto.nombre_canonico}) con '{consulta}':\n")
        for indice, (slug, oferta) in enumerate(candidatos):
            marca = f"  [{oferta.marca}]" if oferta.marca else ""
            print(f"  {indice:2}  ${oferta.precio_cop:>8,}  {slug:13} {oferta.nombre[:48]}{marca}")
        print(f"\n{len(candidatos)} candidatos. Encola el que sirva con  --elegir N.")
        return 0

    if not 0 <= elegir < len(candidatos):
        print(f"El indice {elegir} no existe: hay {len(candidatos)} candidatos (0 a {len(candidatos) - 1}).")
        return 1

    slug, oferta = candidatos[elegir]
    encoladas = await _encolar(
        [
            {
                "id": _uuid_estable("util", slug, oferta.sku),
                "concepto_id": fila_concepto.id,
                "concepto_sugerido": None,
                "texto_origen": fila_concepto.nombre_canonico,
                "tienda_id": slugs[slug],
                "referencia_externa": oferta.sku,
                "url": oferta.url or None,
                "nombre": oferta.nombre[:512],
                "marca": oferta.marca,
                "ean": _ean_valido(oferta.ean),
                "imagen_url": oferta.imagen_url,
                "especificaciones": oferta.especificaciones or {},
                "precio_centavos": oferta.precio_cop * 100,
                "disponible": oferta.disponible,
                "nivel_sugerido": None,
                "puntaje": 0.6,
                "estado": "pendiente",
                "origen": "manual",
                "version_lista_id": revision.version_id,
                "item_lista_id": None,
            }
        ]
    )
    if not encoladas:
        print(f"Ese producto de {slug} ya estaba propuesto.")
        return 0
    print(f"Encolado para {concepto}: {oferta.nombre[:50]}")
    print(f"  ${oferta.precio_cop:,}  {slug}")
    print("Elige su nivel y apruebalo con  --aprobar ID --nivel <economico|confiable|premium>.")
    return 0


async def cerrar(id_corto: str) -> int:
    from sqlalchemy import Text, cast, func, select, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    propuesta = Base.metadata.tables["propuesta_producto"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(version.c.id, version.c.revisada_en).where(
                        cast(version.c.id, Text).like(f"{id_corto}%")
                    )
                )
            ).first()
            if fila is None:
                print(f"No existe ninguna version que empiece por {id_corto}")
                return 1
            if fila.revisada_en is not None:
                print(f"Ya estaba revisada el {fila.revisada_en:%Y-%m-%d}.")
                return 0
            pendientes = (
                await conexion.execute(
                    select(func.count())
                    .select_from(propuesta)
                    .where(propuesta.c.version_lista_id == fila.id, propuesta.c.estado == "pendiente")
                )
            ).scalar_one()
            if pendientes:
                print(f"Quedan {pendientes} propuestas sin decidir de esta lista.")
                print("Resuelvelas antes de cerrar: despues no se puede volver a buscar.")
                return 1
            await conexion.execute(
                update(version).where(version.c.id == fila.id).values(revisada_en=datetime.now(UTC))
            )
    finally:
        await motor.cerrar()
    print("Lista revisada. De aqui en adelante se responde con el catalogo, sin consultar tiendas.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--probar", help="un renglon a resolver SOLO contra nuestra base")
    analizador.add_argument(
        "--desde-lista", type=Path, help="archivo con un renglon por linea, para --probar"
    )
    analizador.add_argument(
        "--listas", action="store_true", help="versiones de lista y su estado de revision"
    )
    analizador.add_argument("--revisar", metavar="VERSION", help="revisar una version sin revisar")
    analizador.add_argument("--cerrar", metavar="VERSION", help="dar por revisada una version")
    analizador.add_argument("--crear-libro", action="store_true", help="alta a mano, requiere --revisar")
    analizador.add_argument(
        "--crear-util",
        action="store_true",
        help="alta de un util apoyada en las tiendas, requiere --revisar --concepto --consulta",
    )
    analizador.add_argument("--isbn")
    analizador.add_argument("--titulo")
    analizador.add_argument("--precio", type=int, help="en pesos, sin centavos")
    analizador.add_argument("--tienda")
    analizador.add_argument("--url")
    analizador.add_argument("--imagen")
    analizador.add_argument("--concepto", help="codigo del concepto, por ejemplo C048")
    analizador.add_argument("--consulta", help="texto a buscar en las tiendas, para --crear-util")
    analizador.add_argument(
        "--elegir", type=int, metavar="N", help="numero del candidato a encolar, para --crear-util"
    )
    analizador.add_argument("--pendientes", action="store_true")
    analizador.add_argument("--aprobar", metavar="ID")
    analizador.add_argument("--rechazar", metavar="ID")
    analizador.add_argument("--nivel", choices=NIVEL_POR_POSICION)
    analizador.add_argument("--motivo")
    analizador.add_argument(
        "--no-surtir",
        action="store_true",
        help="al rechazar, marca el concepto 'no_comprar': no se lo ofrecemos al papa",
    )
    args = analizador.parse_args()

    if args.listas:
        return asyncio.run(listar_listas()) or 0
    if args.pendientes:
        return asyncio.run(listar_pendientes()) or 0
    if args.aprobar:
        return asyncio.run(resolver(args.aprobar, True, args.nivel, None))
    if args.rechazar:
        return asyncio.run(resolver(args.rechazar, False, None, args.motivo, args.no_surtir))
    if args.cerrar:
        return asyncio.run(cerrar(args.cerrar))

    renglones = []
    if args.probar:
        renglones.append(args.probar)
    if args.desde_lista:
        renglones += [ln.strip() for ln in args.desde_lista.read_text().splitlines() if ln.strip()]
    if renglones:
        return asyncio.run(probar(renglones)) or 0

    if args.crear_libro:
        if not args.revisar:
            print("El alta a mano va dentro de una revision: agrega --revisar <version>.")
            return 2
        faltan = [n for n in ("isbn", "titulo", "precio", "tienda") if getattr(args, n) is None]
        if faltan:
            print(f"Para dar de alta un libro faltan: {', '.join('--' + n for n in faltan)}")
            return 2
        try:
            return asyncio.run(
                crear_libro(
                    args.revisar,
                    args.isbn,
                    args.titulo,
                    args.precio,
                    args.tienda,
                    args.url,
                    args.imagen,
                    args.concepto,
                )
            )
        except PuertaCerrada as error:
            print(error)
            return 1

    if args.crear_util:
        if not args.revisar:
            print("El alta de un util va dentro de una revision: agrega --revisar <version>.")
            return 2
        faltan = [n for n in ("concepto", "consulta") if getattr(args, n) is None]
        if faltan:
            print(f"Para dar de alta un util faltan: {', '.join('--' + n for n in faltan)}")
            return 2
        try:
            return asyncio.run(crear_util(args.revisar, args.concepto, args.consulta, args.elegir))
        except PuertaCerrada as error:
            print(error)
            return 1

    if args.revisar:
        try:
            revision = asyncio.run(abrir_revision(args.revisar))
        except PuertaCerrada as error:
            print(error)
            return 1
        return asyncio.run(proponer(revision)) or 0

    analizador.print_help()
    return 2


TIENDAS_LIBROS: dict[str, str] = {
    "buscalibre": "https://www.buscalibre.com.co",
    "libreria_nacional": "https://www.librerianacional.com",
}

SLUG_TIENDA_LIBRO = {"buscalibre": "buscalibre", "libreria_nacional": "librerianacional"}

_RUTA_BUSQUEDA = {
    "buscalibre": "/libros/search?q=",
    "libreria_nacional": "/api/catalog_system/pub/products/search?ft=",
}


def consulta_libro_en(tienda: str, titulo: str, isbn13: str | None) -> str:
    termino = (normalizar_isbn(isbn13) if isbn13 else None) or titulo.strip()
    return TIENDAS_LIBROS[tienda] + _RUTA_BUSQUEDA[tienda] + urllib.parse.quote(termino)


def consulta_libro(titulo: str, isbn13: str | None) -> str:
    return consulta_libro_en("buscalibre", titulo, isbn13)


def _precio_cop(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).split(",")[0]
    return re.sub(r"\D", "", texto)


def fila_libro(
    tienda: str,
    bruto: dict,
    *,
    concepto_codigo: str = "",
    nivel: str = "confiable",
    observado_en: str | None = None,
) -> dict[str, str]:
    if tienda not in TIENDAS_LIBROS:
        raise ValueError(f"tienda de libros desconocida: {tienda!r}")

    def texto(clave: str) -> str:
        v = bruto.get(clave)
        return "" if v is None else str(v).strip()

    isbn = normalizar_isbn(texto("isbn13")) if texto("isbn13") else None
    atributos = bruto.get("atributos")
    return {
        "concepto_codigo": texto("concepto_codigo") or concepto_codigo,
        "titulo": texto("titulo"),
        "isbn13": isbn or "",
        "editorial": texto("editorial"),
        "nivel": texto("nivel") or nivel,
        "tienda_slug": SLUG_TIENDA_LIBRO[tienda],
        "precio_cop": _precio_cop(bruto.get("precio")),
        "imagen_url": texto("imagen_url"),
        "url_origen": texto("url_origen"),
        "disponible": texto("disponible") or "true",
        "sku_tienda": texto("sku_tienda"),
        "observado_en": observado_en or datetime.now(UTC).date().isoformat(),
        "atributos": json.dumps(atributos, ensure_ascii=False)
        if isinstance(atributos, dict) and atributos
        else "",
    }


if __name__ == "__main__":
    sys.exit(main())
