"""Llena los huecos del catalogo: conceptos sin producto y niveles sin opcion.

Decisiones:
- Los productos salen de la API de catalogo de VTEX (Exito y Panamericana), que devuelve nombre,
  precio, existencias, EAN e imagen en una sola consulta.
- Cada concepto trae su consulta y su rango de precio escritos a mano: preguntar "gel antibacterial"
  devuelve primero una garrafa de veinte litros, una respuesta absurda para una lista de primaria.
- Lo cargado entra con `quality_score` bajo: son sugerencias de una maquina y el administrador debe
  poder distinguirlas en la cola de revision.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .cargador import _uuid_estable

CONSULTAS: dict[str, tuple[str, int, int]] = {
    "C024": ("bata laboratorio escolar", 20000, 120000),
    "C025": ("tabla periodica escolar", 1000, 30000),
    "C026": ("calculadora cientifica escolar", 15000, 150000),
    "C032": ("resma papel carta", 8000, 60000),
    "C033": ("palitos de paleta manualidades", 1500, 25000),
    "C038": ("lana madeja ovillo", 2000, 30000),
    "C040": ("toallas humedas panitos", 3000, 30000),
    "C046": ("tabla picado", 3000, 20000),
    "C043": ("lentejuelas", 2000, 20000),
    "C055": ("refuerzo hojas", 1000, 15000),
    "C047": ("algodon", 1500, 25000),
    "C073": ("punzon", 1000, 6000),
    "C099": ("plantilla mapa colombia", 1500, 10000),
    "C097": ("esponja lavar loza", 2000, 12000),
    "C048": ("biblia catolica letra grande", 60000, 400000),
    "C054": ("juego didactico educativo ninos", 10000, 90000),
    "C056": ("rompecabezas infantil 100 piezas", 8000, 70000),
    "C057": ("vaso plastico", 3000, 40000),
    "C060": ("curvigrafo", 3000, 45000),
    "C062": ("guantes desechables caja", 5000, 50000),
    "C063": ("gafas natacion", 8000, 95000),
    "C066": ("flauta dulce soprano", 15000, 90000),
    "C068": ("ojos moviles manualidades", 1500, 20000),
    "C070": ("set arte", 8000, 90000),
    "C071": ("protoboard", 8000, 150000),
    "C072": ("lazo saltar cuerda", 5000, 45000),
    "C074": ("balon futbol", 20000, 120000),
    "C075": ("bolsa basura rollo", 3000, 35000),
    "C077": ("cojin infantil", 15000, 90000),
    "C078": ("fichas bibliograficas", 2000, 25000),
    "C079": ("pandereta instrumento percusion", 10000, 90000),
    "C080": ("jabon liquido manos", 3000, 35000),
    "C081": ("abaco escolar", 8000, 70000),
    "C084": ("gel antibacterial 500 ml", 3000, 35000),
    "C087": ("pilas alcalinas AA", 4000, 45000),
    "C088": ("pintura facial", 5000, 50000),
    "C089": ("pompones manualidades", 2000, 25000),
    "C090": ("separadores hojas indice", 2000, 25000),
    "C092": ("tablero de dibujo tecnico", 15000, 120000),
    "C093": ("tinta china dibujo", 5000, 50000),
    "C095": ("arena decorativa manualidades", 2000, 25000),
    "C096": ("copitos algodon", 2000, 20000),
    "C098": ("plastico burbuja rollo", 5000, 60000),
    "C002": ("lapiz negro", 500, 20000),
    "C008": ("regla", 1000, 15000),
    "C009": ("cartuchera", 5000, 60000),
    "C012": ("esfero", 500, 20000),
    "C016": ("pegante barra", 1500, 20000),
    "C021": ("pincel", 1500, 25000),
    "C027": ("tempera", 2000, 40000),
    "C030": ("acetato", 1000, 25000),
    "C039": ("resaltador", 1500, 25000),
    "C049": ("delantal", 10000, 60000),
    "C050": ("lienzo", 5000, 70000),
    "C059": ("corrector", 1500, 20000),
    "C061": ("aserrin", 1500, 20000),
    "C091": ("sobre manila", 500, 15000),
    "C086": ("morral escolar", 20000, 90000),
}

SURTIDO: dict[str, list[tuple[str, int, int]]] = {
    "C003": [("block iris", 2000, 20000), ("block cuadriculado", 3000, 40000)],
    "C006": [
        ("marcador borrable", 3000, 30000),
        ("marcador permanente", 2000, 30000),
        ("marcador sharpie", 3000, 40000),
        ("marcador pelikan", 2000, 30000),
    ],
    "C012": [
        ("esfero bic", 500, 20000),
        ("esfero kilometrico", 500, 20000),
        ("esfero gel", 1000, 25000),
        ("esfero paper mate", 1000, 25000),
    ],
    "C004": [
        ("colores prismacolor", 8000, 90000),
        ("colores norma", 5000, 60000),
        ("crayones crayola", 3000, 40000),
        ("colores faber", 8000, 90000),
    ],
    "C010": [("cartulina escolar", 2000, 20000)],
    "C014": [
        ("papel seda", 1000, 20000),
        ("papel crepe", 1000, 20000),
        ("papel silueta", 1000, 20000),
        ("papel kraft", 1000, 25000),
    ],
    "C020": [("vinilo acrilico", 2000, 40000), ("vinilo escolar", 3000, 40000)],
    "C022": [("plastilina pelikan", 3000, 30000), ("plastilina barra", 2000, 30000)],
    "C027": [("pintura oleo", 5000, 60000), ("oleo", 5000, 60000)],
    "C029": [("foamy", 3000, 40000)],
    "C038": [("lana madeja", 2000, 30000)],
    "C051": [("tempera", 3000, 60000)],
    "C001": [("cuaderno cosido", 5000, 30000), ("cuaderno argollado", 8000, 45000)],
    "C039": [("resaltador kiut", 5000, 30000), ("resaltador pastel", 3000, 30000)],
    "C086": [("morral infantil", 30000, 130000), ("morral disney", 25000, 150000)],
    "C071": [("kit electronica", 20000, 150000), ("protoboard", 5000, 150000), ("arduino", 15000, 400000)],
}

CONCEPTOS_PAQUETE = frozenset({"C010", "C051", "C020", "C029", "C022", "C038", "C014"})

SIN_CONSULTA_FIABLE = ("C035", "C069")


NO_SE_SURTE = {
    "C067": "El colegio pide una muda de ropa del nino. No hay que comprarla: se manda una que ya tenga.",
}

from .tiendas import _coincide  # noqa: E402

_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

TIENDAS = (("exito", "www.exito.com"), ("panamericana", "www.panamericana.com.co"))


@dataclass(frozen=True)
class Candidato:
    tienda: str
    nombre: str
    precio_cop: int
    imagen_url: str
    url: str
    ean: str | None
    sku: str
    marca: str | None


def buscar(host: str, consulta: str, cuantos: int = 24, intentos: int = 3) -> list[dict[str, Any]]:
    direccion = (
        f"https://{host}/api/catalog_system/pub/products/search"
        f"?ft={urllib.parse.quote(consulta)}&_from=0&_to={cuantos - 1}"
    )
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(direccion, headers=_NAVEGADOR), timeout=25
            ) as respuesta:
                datos = json.loads(respuesta.read())
            if isinstance(datos, list) and datos:
                return datos
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        if intento < intentos - 1:
            time.sleep(1.5 * (intento + 1))
    return []


def a_candidatos(
    slug: str,
    crudos: list[dict[str, Any]],
    minimo: int,
    maximo: int,
    consulta: str = "",
) -> list[Candidato]:
    salida = []
    for crudo in crudos:
        if consulta and not _coincide(crudo.get("productName") or "", consulta):
            continue
        for articulo in crudo.get("items", []):
            vendedores = articulo.get("sellers") or []
            if not vendedores:
                continue
            oferta = vendedores[0].get("commertialOffer") or {}
            precio = int(oferta.get("Price") or 0)
            if precio <= 0 or not (minimo <= precio <= maximo):
                continue
            if (oferta.get("AvailableQuantity") or 0) <= 0:
                continue
            imagenes = articulo.get("images") or []
            if not imagenes:
                continue
            salida.append(
                Candidato(
                    tienda=slug,
                    nombre=crudo.get("productName") or articulo.get("name") or "",
                    precio_cop=precio,
                    imagen_url=imagenes[0].get("imageUrl", ""),
                    url=crudo.get("link") or "",
                    ean=(articulo.get("ean") or None),
                    sku=str(articulo.get("itemId") or ""),
                    marca=crudo.get("brand") or None,
                )
            )
            break
    return salida


def candidatos_shopify(slug: str, consulta: str, minimo: int, maximo: int) -> list[Candidato]:
    from .tiendas import buscar as buscar_tienda

    salida = []
    for oferta in buscar_tienda(slug, consulta):
        if oferta.precio_cop <= 0 or not (minimo <= oferta.precio_cop <= maximo):
            continue
        if not oferta.disponible or not oferta.imagen_url:
            continue
        salida.append(
            Candidato(
                tienda=slug,
                nombre=oferta.nombre,
                precio_cop=oferta.precio_cop,
                imagen_url=oferta.imagen_url,
                url=oferta.url,
                ean=oferta.ean,
                sku=oferta.sku,
                marca=oferta.marca,
            )
        )
    return salida


def repartir_en_niveles(candidatos: list[Candidato], faltan: set[str]) -> dict[str, Candidato]:
    if not candidatos:
        return {}
    ordenados = sorted(candidatos, key=lambda c: c.precio_cop)
    posicion = {
        "economico": ordenados[len(ordenados) // 6],
        "confiable": ordenados[len(ordenados) // 2],
        "premium": ordenados[min(len(ordenados) - 1, (5 * len(ordenados)) // 6)],
    }
    elegidos: dict[str, Candidato] = {}
    usados: set[str] = set()
    precios_usados: set[int] = set()
    for nivel in ("economico", "confiable", "premium"):
        if nivel not in faltan:
            continue
        preferido = posicion[nivel]
        if preferido.nombre in usados:
            alternativa = next((c for c in ordenados if c.nombre not in usados), None)
            if alternativa is None:
                continue
            preferido = alternativa
        if preferido.precio_cop in precios_usados:
            continue
        elegidos[nivel] = preferido
        usados.add(preferido.nombre)
        precios_usados.add(preferido.precio_cop)
    return elegidos


def consultar_tiendas(
    consulta: str,
    minimo: int,
    maximo: int,
    tiendas: dict[str, uuid.UUID],
    ya_ofrecidos: set[tuple[str, str]],
) -> list[Candidato]:
    with ThreadPoolExecutor(max_workers=3) as par:
        vtex = par.map(
            lambda t: a_candidatos(t[0], buscar(t[1], consulta), minimo, maximo, consulta),
            TIENDAS,
        )
        shopify = par.submit(candidatos_shopify, "grancentral", consulta, minimo, maximo)
        por_tienda = [*vtex, shopify.result()]
    return [
        c
        for grupo_tienda in por_tienda
        for c in grupo_tienda
        if (str(tiendas[c.tienda]), c.sku) not in ya_ofrecidos
    ]


def _a_propuesta(
    codigo: str,
    info: dict[str, Any],
    c: Candidato,
    tiendas: dict[str, uuid.UUID],
    nivel: str | None,
) -> dict[str, Any]:
    return {
        "id": _uuid_estable("sugerido", codigo, c.tienda, c.sku),
        "concepto_id": info["id"],
        "concepto_sugerido": None,
        "texto_origen": info["nombre"],
        "tienda_id": tiendas[c.tienda],
        "referencia_externa": c.sku,
        "url": c.url or None,
        "nombre": c.nombre[:512],
        "marca": c.marca,
        "ean": c.ean if (c.ean or "").isdigit() and len(c.ean or "") in (8, 12, 13) else None,
        "imagen_url": c.imagen_url,
        "precio_centavos": c.precio_cop * 100,
        "disponible": True,
        "especificaciones": {},
        "nivel_sugerido": nivel,
        "puntaje": 0.4,
        "estado": "pendiente",
        "origen": "scraper",
        "version_lista_id": None,
        "item_lista_id": None,
    }


def _preferir_paquetes(candidatos: list[Candidato], attrs: tuple[str, ...]) -> list[Candidato]:
    from .extraccion import extraer_empaque

    con_empaque = [(extraer_empaque(c.nombre, attrs).unidades, c) for c in candidatos]
    paquetes = [par for par in con_empaque if par[0] > 1]
    escogidos = paquetes or con_empaque
    escogidos.sort(key=lambda par: (-par[0], par[1].precio_cop))
    return [c for _, c in escogidos]


async def _estado() -> tuple[
    dict[str, dict[str, Any]], dict[str, set[str]], dict[str, uuid.UUID], set[tuple[str, str]]
]:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    producto = Base.metadata.tables["producto_canonico"]
    tienda = Base.metadata.tables["tienda"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            conceptos = {
                f.codigo: {
                    "id": f.id,
                    "nombre": f.nombre_canonico,
                    "attrs": tuple(f.atributos_discriminantes or ()) + tuple(f.atributos_descriptivos or ()),
                }
                for f in await conexion.execute(
                    select(
                        concepto.c.codigo,
                        concepto.c.id,
                        concepto.c.nombre_canonico,
                        concepto.c.atributos_discriminantes,
                        concepto.c.atributos_descriptivos,
                    )
                )
            }
            niveles: dict[str, set[str]] = {}
            for f in await conexion.execute(
                select(producto.c.concepto_id, producto.c.nivel).where(producto.c.personaje.is_(None))
            ):
                niveles.setdefault(str(f.concepto_id), set()).add(f.nivel)
            tiendas = {f.slug: f.id for f in await conexion.execute(select(tienda.c.slug, tienda.c.id))}
            oferta = Base.metadata.tables["oferta_tienda"]
            ya_ofrecidos = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(select(oferta.c.tienda_id, oferta.c.referencia_externa))
            }
    finally:
        await motor.cerrar()
    return conceptos, niveles, tiendas, ya_ofrecidos


async def _encolar_candidatos(propuestas: list[dict[str, Any]], tipos_item) -> int:
    from sqlalchemy import bindparam, update
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    motor = crear_motor("catalogo")
    encoladas = 0
    try:
        async with motor.engine.begin() as conexion:
            if propuestas:
                tabla = Base.metadata.tables["propuesta_producto"]
                resultado = await conexion.execute(
                    insert(tabla)
                    .values(propuestas)
                    .on_conflict_do_nothing(constraint="uq_propuesta_referencia")
                )
                encoladas = resultado.rowcount or 0
            if tipos_item:
                concepto = Base.metadata.tables["concepto"]
                await conexion.execute(
                    update(concepto)
                    .where(concepto.c.codigo == bindparam("cod"))
                    .values(tipo_item=bindparam("tipo")),
                    tipos_item,
                )
    finally:
        await motor.cerrar()
    return encoladas


async def _principal(solo_validar: bool) -> int:
    conceptos, niveles, tiendas, ya_ofrecidos = await _estado()

    pendientes = []
    for codigo, (consulta, minimo, maximo) in CONSULTAS.items():
        info = conceptos.get(codigo)
        if info is None:
            print(f"  aviso: el concepto {codigo} ya no existe, se omite")
            continue
        faltan = {"economico", "confiable", "premium"} - niveles.get(str(info["id"]), set())
        if faltan:
            pendientes.append((codigo, info, consulta, minimo, maximo, faltan))

    print(f"Conceptos con huecos: {len(pendientes)}. Consultando las tres tiendas...")

    def todas_las_tiendas(consulta: str, minimo: int, maximo: int) -> list[Candidato]:
        return consultar_tiendas(consulta, minimo, maximo, tiendas, ya_ofrecidos)

    resultados = []
    for indice, (codigo, info, consulta, minimo, maximo, faltan) in enumerate(pendientes, 1):
        candidatos = todas_las_tiendas(consulta, minimo, maximo)
        resultados.append((codigo, info, faltan, repartir_en_niveles(candidatos, faltan), len(candidatos)))
        avance = f"[{indice:2}/{len(pendientes)}]"
        print(f"  {avance} {codigo} {info['nombre'][:22]:24} {len(candidatos):3} candidatos")
        time.sleep(0.4)

    propuestas = []
    cerrados = parciales = vacios = 0

    for codigo, info, faltan, elegidos, cuantos in resultados:
        if not elegidos:
            vacios += 1
            print(f"  {codigo:6} {info['nombre'][:24]:26} SIN CANDIDATOS ({cuantos} vistos, fuera de rango)")
            continue
        if len(elegidos) == len(faltan):
            cerrados += 1
        else:
            parciales += 1

        for nivel, c in elegidos.items():
            print(f"      {nivel:10} ${c.precio_cop:>7}  {c.nombre[:52]}")
            propuestas.append(_a_propuesta(codigo, info, c, tiendas, nivel))

    tipos = [{"cod": c, "tipo": "no_comprar"} for c in NO_SE_SURTE if c in conceptos]

    print("\n=== huecos ===")
    print(f"  conceptos con candidatos para los 3 niveles  {cerrados}")
    print(f"  con candidatos a medias                      {parciales}")
    print(f"  sin ningun candidato aceptable               {vacios}")
    print(f"  candidatos encolados para revision           {len(propuestas)}")
    print(f"  conceptos marcados como no surtibles         {len(tipos)}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    encoladas = await _encolar_candidatos(propuestas, tipos)
    print(f"\nEncolado. {encoladas} candidatos nuevos en la cola de revision.")
    print("Revisalos con  make bd-revisar  /  python -m tukit_catalogo.descubrir --pendientes")
    return 0


async def _surtir(codigos: list[str], tope: int, solo_validar: bool) -> int:
    conceptos, _niveles, tiendas, ya_ofrecidos = await _estado()

    codigos = [c.upper() for c in codigos]
    desconocidos = [c for c in codigos if c not in SURTIDO]
    if desconocidos:
        print(f"  aviso: sin consultas de surtido para {', '.join(desconocidos)}; se omiten")
    a_surtir = [c for c in codigos if c in SURTIDO]
    if not a_surtir:
        print("Nada que surtir: ninguno de los codigos tiene consultas en SURTIDO.")
        return 1

    print(f"Ensanchando {len(a_surtir)} conceptos. Consultando las tres tiendas...")

    propuestas: dict[Any, dict[str, Any]] = {}
    for codigo in a_surtir:
        info = conceptos.get(codigo)
        if info is None:
            print(f"  aviso: el concepto {codigo} ya no existe, se omite")
            continue
        for consulta, minimo, maximo in SURTIDO[codigo]:
            candidatos = consultar_tiendas(consulta, minimo, maximo, tiendas, ya_ofrecidos)
            if codigo in CONCEPTOS_PAQUETE:
                candidatos = _preferir_paquetes(candidatos, info["attrs"])
            else:
                candidatos = sorted(candidatos, key=lambda c: c.precio_cop)
            recortados = candidatos[:tope]
            print(
                f"  {codigo:6} {info['nombre'][:20]:22} '{consulta}': "
                f"{len(candidatos):3} candidatos, encolo {len(recortados)}"
            )
            for c in recortados:
                fila = _a_propuesta(codigo, info, c, tiendas, None)
                propuestas.setdefault(fila["id"], fila)
            time.sleep(0.4)

    filas = list(propuestas.values())
    print(f"\n=== ensanchamiento ===\n  candidatos unicos encolables  {len(filas)}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    encoladas = await _encolar_candidatos(filas, [])
    print(f"\nEncolado. {encoladas} candidatos nuevos en la cola de revision.")
    print("Revisalos con  make bd-revisar  /  python -m tukit_catalogo.descubrir --pendientes")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--solo-validar", action="store_true")
    analizador.add_argument(
        "--surtir",
        metavar="CODIGO[,CODIGO...]",
        help="Ensancha los conceptos dados: encola el abanico completo, no solo los niveles faltantes.",
    )
    analizador.add_argument(
        "--tope",
        type=int,
        default=15,
        help="Maximo de candidatos a encolar por consulta en --surtir (por defecto 15).",
    )
    args = analizador.parse_args()
    if args.surtir:
        codigos = [c.strip() for c in args.surtir.split(",") if c.strip()]
        return asyncio.run(_surtir(codigos, args.tope, args.solo_validar))
    return asyncio.run(_principal(args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
