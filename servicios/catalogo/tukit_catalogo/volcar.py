"""Vuelca de la base a los CSV curados, para cerrar el circulo de reproducibilidad.

El flujo del catalogo era asimetrico y ahi estaba el defecto de fondo. `cargador`
lee CSV -> base, pero `completar` escribe base y NUNCA exportaba de vuelta: los
productos que trajo del mayorista (grancentral) y de las dos minoristas quedaban
solo en Postgres. La consecuencia es que el corpus versionado en
`datos/catalogo/*.csv` quedaba una sesion atras de la base viva, y una carga
limpia desde el CSV ya no reproducia el catalogo que se habia armado. Para una
tesis donde el CSV DEBE ser la fuente de verdad que `make bd-cargar` reproduce,
eso es inaceptable: el estado bueno vivia en un contenedor efimero.

Este modulo es la mitad que faltaba. Vuelca `producto_canonico`, `oferta_tienda`
y `precio_oferta` de la base a los tres CSV, en el MISMO formato y orden de
columnas que `cargador` espera leer. El invariante que persigue es de ida y
vuelta: tras `bd-cargar && bd-completar && bd-volcar`, una segunda `bd-cargar`
sobre base limpia reproduce el MISMO estado.

Tres decisiones que no son de comodidad sino de correccion:

1. **Fusion, no volcado.** Las filas que YA estan en el CSV se conservan tal
   cual, byte a byte. No se re-serializan desde la base. Es lo unico que respeta
   la curaduria: el CSV es dueno de columnas que la base tiene distintas a
   proposito (`atributos`, `texto_embedding`, `nivel` reacomodado por `nivelar`,
   las fechas). Reescribirlas desde la base desharia ese trabajo igual que el
   upsert deshacia el enriquecimiento antes de `COLUMNAS_ENRIQUECIDAS`. Solo se
   AGREGAN las filas nuevas que la base tiene y el CSV no.

2. **Solo se vuelca lo CURADO, no lo candidato ni lo sintetizado.** Tres clases
   de fila viven en `producto_canonico` y solo una pertenece al corpus:

   - Libros (`TK-LIB-*`): `cargador._libros()` los SINTETIZA desde
     `libros_firecrawl.csv` en cada carga. Volcarlos los duplicaria -dos fuentes
     para la misma fila-, que es justo lo que el `_uuid_estable` por ISBN evita.
   - Sugerencias de maquina (`TK-SUG-*`, `TMP-*`): las trajo `completar` de una
     tienda con un rango de precio, calidad 0,4, SIN que una persona las mirara.
     No son catalogo: son candidatos que pertenecen a la cola `propuesta_producto`
     hasta que un administrador los apruebe. Versionarlas meteria al corpus de la
     tesis basura que el quinto filtro no atrapo (una poinsettia entrando como
     lentejuela, un lavaloza como esponja). Se excluyen a proposito.
   - Lo curado: filas del curador humano y las aprobadas en revision
     (`TK-REV-*`, calidad 0,85). ESTO si es catalogo y esto es lo que el papa ve,
     asi que esto es lo unico que se vuelca. Las aprobadas son, ademas, la razon
     de ser del cache: una vez revisadas quedan en casa para la siguiente lista.

   Se excluyen tambien las ofertas y precios que cuelgan de las filas excluidas.

3. **Orden estable.** Se ordena por `sku_interno`/`id` para que el diff del CSV
   sea revisable y la exportacion sea determinista: dos volcados de la misma base
   dan el mismo fichero byte a byte.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any

from .cargador import AGENTE_FIRECRAWL, leer_csv

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

# Prefijos de SKU que NO son catalogo curado y por tanto no se vuelcan.
#   TK-LIB-  libros, re-sintetizados desde libros_firecrawl.csv en cada carga.
#   TK-SUG-  sugerencias de `completar`: candidatos de tienda, calidad 0,4.
#   TMP-     staging de corridas viejas de completar/enriquecer, sin revisar.
# Ver la decision 2 del modulo: solo lo curado por una persona o aprobado en
# revision (TK-REV-, calidad 0,85) llega al corpus versionado.
PREFIJOS_NO_CURADOS = ("TK-LIB-", "TK-SUG-", "TMP-")


def _es_curado(sku: str | None, curado_por: Any) -> bool:
    """Una fila es catalogo si la puso una persona o la aprobo una revision.

    Dos senales, y basta con que UNA la descalifique. El prefijo del SKU marca
    la procedencia (libro sintetizado, sugerencia de maquina, staging), y
    `curado_por = AGENTE_FIRECRAWL` marca lo que trajo el raspado sin que nadie
    lo mirara. Se cruzan las dos a proposito: si una corrida futura de
    `completar` cambia el esquema de SKU, el filtro por agente sigue atajando la
    basura; y las filas aprobadas en revision (TK-REV-) llevan el agente como
    `curado_por` pero SI son catalogo, asi que el prefijo las rescata.
    """
    sku = sku or ""
    if sku.startswith("TK-REV-"):
        return True
    if sku.startswith(PREFIJOS_NO_CURADOS):
        return False
    return str(curado_por) != str(AGENTE_FIRECRAWL)


# Cabeceras exactas de cada CSV, en el orden en que `cargador` las lee. No se
# derivan de la base: la base tiene columnas que el CSV no versiona (embedding,
# corrida_id) y el CSV tiene columnas que la base rellena aparte. Fijarlas aqui
# es lo que garantiza que el fichero volcado sea leible por `cargador` sin
# sorpresas de orden ni de columnas de mas.
COLUMNAS_PRODUCTO = [
    "id",
    "concepto_id",
    "ean",
    "sku_interno",
    "nombre",
    "descripcion",
    "marca",
    "nivel",
    "personaje",
    "imagen_url",
    "atributos",
    "ruta_categoria",
    "es_propio",
    "grupo_variante_id",
    "es_representante_canonico",
    "embedding",
    "embedding_model",
    "texto_embedding",
    "quality_score",
    "activo",
    "curado_por",
    "curado_en",
]
COLUMNAS_OFERTA = [
    "id",
    "producto_canonico_id",
    "tienda_id",
    "referencia_externa",
    "url",
    "metodo_vinculacion",
    "confianza_vinculacion",
    "disponible",
    "activo",
    "visto_en",
]
COLUMNAS_PRECIO = [
    "id",
    "oferta_id",
    "valor_centavos",
    "moneda",
    "fuente",
    "vigente_desde",
    "vigente_hasta",
    "corrida_id",
]


# ---------------------------------------------------------------------------
# Serializacion base -> texto CSV
#
# Cada helper invierte lo que el parser de `cargador` hace al leer, de forma que
# el valor vuelva a entrar identico. La regla comun: un nulo se escribe como
# cadena vacia, porque asi lo lee `_texto` de vuelta a None.
# ---------------------------------------------------------------------------


def _s(valor: Any) -> str:
    """Texto o vacio. None y '' colapsan a '' (como los lee `_texto`)."""
    return "" if valor is None else str(valor)


def _bool_csv(valor: Any) -> str:
    """Booleano al 'true'/'false' que usan los CSV; None a vacio.

    `disponible` es el unico que admite nulo de verdad (no-se, no no-hay), y ahi
    el vacio importa: `_bool(por_omision=True)` lo lee como disponible, que es la
    lectura correcta de una observacion que falta.
    """
    if valor is None:
        return ""
    return "true" if valor else "false"


def _num3(valor: Any) -> str:
    """Numeric(4,3) con tres decimales, como lo escribe el corpus (0.400, 1.000)."""
    return "" if valor is None else f"{float(valor):.3f}"


def _fecha_csv(valor: Any) -> str:
    """timestamptz a ISO 8601. `_fecha` de `cargador` lo lee con `fromisoformat`."""
    return "" if valor is None else valor.isoformat()


def _atributos_csv(valor: Any) -> str:
    """dict/JSON de atributos a su forma de cadena.

    `cargador._productos()` FUERZA `atributos` a `{}` al leer (los atributos
    reales los siembra `enriquecer` en la base, no el CSV). Asi que este valor no
    afecta la carga; se conserva por fidelidad para que el CSV volcado se parezca
    al de la base y el diff cuente la verdad de lo que hay.
    """
    if not valor:
        return "{}"
    if isinstance(valor, str):
        return valor
    import json

    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def _fila_producto(p: Any) -> dict[str, str]:
    return {
        "id": _s(p.id),
        "concepto_id": _s(p.concepto_id),
        "ean": _s(p.ean),
        "sku_interno": _s(p.sku_interno),
        "nombre": _s(p.nombre),
        "descripcion": _s(p.descripcion),
        "marca": _s(p.marca),
        "nivel": _s(p.nivel),
        "personaje": _s(p.personaje),
        "imagen_url": _s(p.imagen_url),
        "atributos": _atributos_csv(p.atributos),
        "ruta_categoria": _s(p.ruta_categoria),
        "es_propio": _bool_csv(p.es_propio),
        "grupo_variante_id": _s(p.grupo_variante_id),
        "es_representante_canonico": _bool_csv(p.es_representante_canonico),
        # El embedding no se versiona en el CSV: es un vector de 1024 flotantes
        # que `enriquecer` recalcula, no un dato curado. Se deja vacio a
        # proposito, igual que en el corpus actual.
        "embedding": "",
        "embedding_model": _s(p.embedding_model),
        "texto_embedding": _s(p.texto_embedding),
        "quality_score": _num3(p.quality_score),
        "activo": _bool_csv(p.activo),
        "curado_por": _s(p.curado_por),
        "curado_en": _fecha_csv(p.curado_en),
    }


def _fila_oferta(o: Any) -> dict[str, str]:
    return {
        "id": _s(o.id),
        "producto_canonico_id": _s(o.producto_canonico_id),
        "tienda_id": _s(o.tienda_id),
        "referencia_externa": _s(o.referencia_externa),
        "url": _s(o.url),
        "metodo_vinculacion": _s(o.metodo_vinculacion),
        "confianza_vinculacion": _num3(o.confianza_vinculacion),
        "disponible": _bool_csv(o.disponible),
        "activo": _bool_csv(o.activo),
        "visto_en": _fecha_csv(o.visto_en),
    }


def _fila_precio(pr: Any) -> dict[str, str]:
    return {
        "id": _s(pr.id),
        "oferta_id": _s(pr.oferta_id),
        "valor_centavos": _s(pr.valor_centavos),
        "moneda": _s(pr.moneda),
        "fuente": _s(pr.fuente),
        "vigente_desde": _fecha_csv(pr.vigente_desde),
        "vigente_hasta": _fecha_csv(pr.vigente_hasta),
        "corrida_id": _s(pr.corrida_id),
    }


# ---------------------------------------------------------------------------
# Fusion y escritura
# ---------------------------------------------------------------------------


def _fusionar(
    existentes: list[dict[str, str]],
    nuevas_por_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    """Conserva las filas del CSV tal cual y agrega solo las que faltan.

    Una fila cuyo `id` ya esta en el CSV NO se toca: el CSV es dueno de sus
    columnas curadas (decision 1 del modulo). Devuelve la lista fusionada y
    cuantas filas nuevas se agregaron.
    """
    vistos = {fila["id"] for fila in existentes}
    agregadas = [fila for id_, fila in nuevas_por_id.items() if id_ not in vistos]
    return existentes + agregadas, len(agregadas)


def _guardar(nombre: str, columnas: list[str], filas: list[dict[str, str]], clave: str) -> None:
    """Escribe el CSV ordenado por `clave` para que el diff sea estable."""
    ruta = DATOS / f"{nombre}.csv"
    ordenadas = sorted(filas, key=lambda f: f[clave])
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(ordenadas)


async def _leer_base() -> dict[str, list[Any]]:
    """Trae las tres tablas de la base viva.

    Mismo patron que `completar._estado`: motor por servicio, una transaccion de
    lectura, cierre en `finally`. No se usa ORM porque solo se necesitan las
    columnas planas para serializar, no las relaciones.
    """
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    oferta = Base.metadata.tables["oferta_tienda"]
    precio = Base.metadata.tables["precio_oferta"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            productos = list(await conexion.execute(select(producto)))
            ofertas = list(await conexion.execute(select(oferta)))
            precios = list(await conexion.execute(select(precio)))
    finally:
        await motor.cerrar()
    return {"productos": productos, "ofertas": ofertas, "precios": precios}


async def _principal(solo_ensayo: bool) -> int:
    datos = await _leer_base()

    # Solo lo curado llega al corpus (decision 2). Lo demas -libros sintetizados,
    # sugerencias de maquina, staging- se descarta junto con sus ofertas y
    # precios, para no arrastrar filas colgando de un producto que no se vuelca.
    ids_excluidos = {str(p.id) for p in datos["productos"] if not _es_curado(p.sku_interno, p.curado_por)}
    productos_bd = [p for p in datos["productos"] if str(p.id) not in ids_excluidos]
    ofertas_bd = [o for o in datos["ofertas"] if str(o.producto_canonico_id) not in ids_excluidos]
    ids_oferta_excluida = {
        str(o.id) for o in datos["ofertas"] if str(o.producto_canonico_id) in ids_excluidos
    }
    precios_bd = [pr for pr in datos["precios"] if str(pr.oferta_id) not in ids_oferta_excluida]

    prod_nuevas = {str(p.id): _fila_producto(p) for p in productos_bd}
    ofe_nuevas = {str(o.id): _fila_oferta(o) for o in ofertas_bd}
    pre_nuevas = {str(pr.id): _fila_precio(pr) for pr in precios_bd}

    prod_fusion, n_prod = _fusionar(leer_csv(DATOS / "productos_canonicos.csv"), prod_nuevas)
    ofe_fusion, n_ofe = _fusionar(leer_csv(DATOS / "ofertas_tienda.csv"), ofe_nuevas)
    pre_fusion, n_pre = _fusionar(leer_csv(DATOS / "precios_oferta.csv"), pre_nuevas)

    print("=== volcado base -> CSV ===")
    omitidos = len(ids_excluidos)
    print(f"  productos: {len(prod_fusion):5} en CSV (+{n_prod} nuevos, {omitidos} no curados omitidos)")
    print(f"  ofertas:   {len(ofe_fusion):5} en CSV (+{n_ofe} nuevas)")
    print(f"  precios:   {len(pre_fusion):5} en CSV (+{n_pre} nuevos)")

    if solo_ensayo:
        print("\nEnsayo. Sin --escribir no se toca ningun fichero.")
        return 0

    _guardar("productos_canonicos", COLUMNAS_PRODUCTO, prod_fusion, "sku_interno")
    _guardar("ofertas_tienda", COLUMNAS_OFERTA, ofe_fusion, "id")
    _guardar("precios_oferta", COLUMNAS_PRECIO, pre_fusion, "id")
    print("\nEscrito. Corre `make bd-datos` para confirmar la cobertura desde el CSV.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vuelca el catalogo de la base a los CSV curados.")
    parser.add_argument(
        "--escribir",
        action="store_true",
        help="Escribe los CSV. Sin esta bandera solo informa cuantas filas se agregarian.",
    )
    args = parser.parse_args()
    return asyncio.run(_principal(solo_ensayo=not args.escribir))


if __name__ == "__main__":
    raise SystemExit(main())
