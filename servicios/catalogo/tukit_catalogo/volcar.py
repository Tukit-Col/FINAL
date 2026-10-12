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

1. **Espejo de MEMBRESIA, contenido conservado.** La base manda sobre QUE filas
   existen; el CSV manda sobre COMO se ven las que sobreviven. Concretamente:
   - Una fila cuyo producto ya NO esta en la base (el administrador lo borro en
     el dashboard, que es un HARD DELETE) se ELIMINA del CSV. Antes no: la fusion
     era solo-suma y una maleta borrada seguia viva en el corpus, asi que una
     `bd-cargar` limpia la resucitaba. Ese era el defecto que hacia sentir que
     "se perdia el trabajo": la base y el CSV divergian y nadie los reconciliaba.
   - Una fila que SIGUE en la base se conserva del CSV tal cual, byte a byte. No
     se re-serializa desde la base, porque el CSV es dueno de columnas que la
     base tiene distintas a proposito: `nivel` lo reacomoda `nivelar` sobre el
     CSV (no sobre la base), `atributos` los cura una persona, y hay arreglos
     manuales (una URL corregida a mano). Reescribirlas desde la base desharia
     ese trabajo.
   - Las filas NUEVAS que la base tiene y el CSV no se AGREGAN, serializadas
     desde la base (su `nivel` es el que puso `resolver`; `nivelar` lo ordena
     despues).
   El neto: tras `bd-volcar --escribir`, el conjunto de productos del CSV es
   exactamente el de la base viva, y el dashboard deja de divergir del corpus.

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
COLUMNAS_PROCEDENCIA = [
    "producto_id",
    "sku_interno",
    "fichero_fuente",
    "sha256_fichero",
    "indice_en_fichero",
    "tienda_origen",
    "referencia_origen",
    "url_origen",
    "precio_observado_cop",
]

# Marca de procedencia para lo aprobado en la cola de revision. La semilla
# vieja salio de dos ficheros JSON fijados por SHA-256 (feed_scraper,
# grancentral) y su origen es "fichero + linea". Lo que aprueba un
# administrador en `/cola` NO sale de un fichero: lo trajo la API en vivo o
# Firecrawl y lo miro una persona. Su origen versionable es la tienda y la URL
# donde se vio, no un hash de fichero -por eso `sha256_fichero` va vacio aqui y
# el test lo admite para esta fuente (ver `test_todo_producto_dice_de_que_...`).
FUENTE_COLA = "cola_revision"


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

    Es lo que `cargador._productos()` le lleva a otra base: lo que `enriquecer`
    leyo del nombre MAS lo que una persona corrigio a mano en el editor (la
    tabla periodica que dice "26 x 20 cm" y la lista pide "grande"). Antes el
    cargador lo ignoraba y esas correcciones no salian de la base de quien las
    hizo.
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


def _fila_procedencia(
    p: Any,
    oferta: Any,
    slug_por_tienda: dict[str, str],
    cop_por_oferta: dict[str, int],
) -> dict[str, str]:
    """Origen de un producto aprobado en la cola, reconstruido desde su oferta.

    No hay fichero versionado detras -por eso `sha256_fichero` va vacio y
    `fichero_fuente` es la marca `cola_revision`-, pero SI hay un origen
    verificable: la tienda y la URL donde el administrador lo vio, y el precio
    que se observo. `indice_en_fichero` se llena con la referencia externa de la
    tienda (el SKU de Exito/Panamericana), que es la posicion natural del item
    en su catalogo de origen.
    """
    centavos = cop_por_oferta.get(str(oferta.id)) if oferta is not None else None
    return {
        "producto_id": _s(p.id),
        "sku_interno": _s(p.sku_interno),
        "fichero_fuente": FUENTE_COLA,
        "sha256_fichero": "",
        "indice_en_fichero": _s(oferta.referencia_externa) if oferta is not None else "",
        "tienda_origen": slug_por_tienda.get(str(oferta.tienda_id), "") if oferta is not None else "",
        "referencia_origen": _s(oferta.referencia_externa) if oferta is not None else "",
        "url_origen": _s(oferta.url) if oferta is not None else "",
        "precio_observado_cop": "" if centavos is None else str(round(centavos / 100)),
    }


# ---------------------------------------------------------------------------
# Fusion y escritura
# ---------------------------------------------------------------------------


# Columnas de las que el CSV es dueno y la base NO debe pisar al espejar. Son
# las que herramientas que corren SOBRE el CSV producen, o que la base rellena
# distinto a proposito:
#   - `nivel` YA NO: ver la nota debajo de la constante.
#   - `quality_score`: `nivelar` lo deriva del nivel para los SKU semilla.
# `atributos` YA NO esta aqui. Era del CSV cuando el cargador los ignoraba; ahora
# el cargador los lee, y lo que vale es lo de la base: lo que `enriquecer` saco
# del nombre y lo que se corrigio a mano para que el filtro de atributos cumpla.
# NO estan aqui `embedding_model`/`texto_embedding`: son la huella que `enriquecer`
# computa CONTRA la base (el modelo usado y el texto embebido). La base manda sobre
# ellos, asi el espejo REFLEJA que el corpus esta embebido en vez de re-vaciarlos.
# El vector `embedding` en si tampoco se versiona en el CSV, pero eso ya lo resuelve
# `_fila_producto` escribiendolo vacio siempre; no necesita estar en este conjunto.
# Todo lo demas (concepto_id, marca, nombre, imagen_url, ean, descripcion,
# personaje, categoria, activo, curado_*) es autoridad de la base: es lo que el
# administrador edita en el dashboard -reasignar concepto, corregir marca o
# nombre- y por tanto es lo que el espejo debe traer de vuelta.
# `nivel` tampoco: el que se cambia en el editor del back-office vive en la base,
# y conservar el del CSV lo perdia al exportar (y lo revertia en la propia base
# en la siguiente carga). El orden por precio lo sigue imponiendo `nivelar`, que
# `exportar` corre DESPUES de este volcado y antes de recargar.
COLUMNAS_PROPIAS_DEL_CSV = frozenset({"quality_score"})


def _fusionar(
    existentes: list[dict[str, str]],
    nuevas_por_id: dict[str, dict[str, str]],
    ids_vivos: set[str],
) -> tuple[list[dict[str, str]], int, int]:
    """Espeja la membresia de la base para ofertas/precios (sin merge de columnas).

    - Se ELIMINA la fila del CSV cuyo `id` ya no esta en `ids_vivos`.
    - Se CONSERVA tal cual la que sigue viva (estas tablas no tienen columnas que
      el CSV cure aparte; su contenido lo reproduce la base al recargar).
    - Se AGREGA la nueva que la base tiene y el CSV no.

    Devuelve (filas, nuevas_agregadas, eliminadas).
    """
    conservadas = [fila for fila in existentes if fila["id"] in ids_vivos]
    eliminadas = len(existentes) - len(conservadas)
    vistos = {fila["id"] for fila in conservadas}
    agregadas = [fila for id_, fila in nuevas_por_id.items() if id_ not in vistos]
    return conservadas + agregadas, len(agregadas), eliminadas


def _fusionar_productos(
    existentes: list[dict[str, str]],
    nuevas_por_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], int, int]:
    """Espejo por-columna de productos: la base manda salvo lo que cura el CSV.

    Para cada producto vivo en la base:
      - si YA estaba en el CSV, se toma la serializacion de la base y se le
        SOBREPONEN las columnas de `COLUMNAS_PROPIAS_DEL_CSV` que trae el CSV.
        Asi una reasignacion de concepto o una edicion de marca/nombre hecha en
        el dashboard llega al corpus, sin borrar el orden de nivel de `nivelar`.
      - si es NUEVA, entra tal cual la serializo la base.
    Una fila del CSV cuyo producto ya no vive en la base se ELIMINA (borrado en
    el dashboard). Devuelve (filas, nuevas, eliminadas).
    """
    csv_por_id = {fila["id"]: fila for fila in existentes}
    salida: list[dict[str, str]] = []
    nuevas = 0
    for id_, fila_bd in nuevas_por_id.items():
        vieja = csv_por_id.get(id_)
        if vieja is None:
            salida.append(fila_bd)
            nuevas += 1
            continue
        fila = dict(fila_bd)
        for col in COLUMNAS_PROPIAS_DEL_CSV:
            if col in vieja:
                fila[col] = vieja[col]
        salida.append(fila)
    eliminadas = len(existentes) - (len(salida) - nuevas)
    return salida, nuevas, eliminadas


def _fusionar_procedencia(
    existentes: list[dict[str, str]],
    nuevas_por_producto: dict[str, dict[str, str]],
    productos_vivos: set[str],
) -> tuple[list[dict[str, str]], int, int]:
    """Como `_fusionar` pero con clave `producto_id`.

    La procedencia se identifica por el producto al que describe, no por un `id`
    propio -no tiene uno-. Se elimina la procedencia de un producto que ya no
    esta vivo, se conserva la de los que siguen (la semilla fijada por hash entre
    ellos), y se agrega la de los productos que el CSV aun no tenia.
    """
    conservadas = [fila for fila in existentes if fila["producto_id"] in productos_vivos]
    eliminadas = len(existentes) - len(conservadas)
    # El SKU no es procedencia, es el nombre vigente del producto: si se re-acuno
    # al reclasificarlo, la fila conservada lo toma de la base. Lo demas (fichero,
    # hash, indice) es la huella de origen y no se toca.
    for fila in conservadas:
        nueva = nuevas_por_producto.get(fila["producto_id"])
        if nueva is not None:
            fila["sku_interno"] = nueva["sku_interno"]
    vistos = {fila["producto_id"] for fila in conservadas}
    agregadas = [fila for pid, fila in nuevas_por_producto.items() if pid not in vistos]
    return conservadas + agregadas, len(agregadas), eliminadas


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
    tienda = Base.metadata.tables["tienda"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            productos = list(await conexion.execute(select(producto)))
            ofertas = list(await conexion.execute(select(oferta)))
            precios = list(await conexion.execute(select(precio)))
            tiendas = list(await conexion.execute(select(tienda)))
    finally:
        await motor.cerrar()
    return {"productos": productos, "ofertas": ofertas, "precios": precios, "tiendas": tiendas}


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

    # Procedencia: cada producto nuevo necesita una fila de origen o el corpus
    # queda con productos sin fichero de procedencia (lo que el test exige). Se
    # elige UNA oferta por producto -la de menor precio, la que `nivelar` habria
    # tomado como representante- y de ella salen tienda, URL y precio observado.
    slug_por_tienda = {str(t.id): t.slug for t in datos["tiendas"]}
    cop_por_oferta = {str(pr.oferta_id): pr.valor_centavos for pr in precios_bd}
    ofertas_por_producto: dict[str, list[Any]] = {}
    for o in ofertas_bd:
        ofertas_por_producto.setdefault(str(o.producto_canonico_id), []).append(o)

    def _oferta_representante(pid: str) -> Any:
        ofs = ofertas_por_producto.get(pid, [])
        if not ofs:
            return None
        return min(ofs, key=lambda o: cop_por_oferta.get(str(o.id), 1 << 62))

    proc_nuevas = {
        str(p.id): _fila_procedencia(p, _oferta_representante(str(p.id)), slug_por_tienda, cop_por_oferta)
        for p in productos_bd
    }

    # La membresia viva la definen las filas curadas de la base: sus `id` (y para
    # procedencia, los `id` de producto). Una fila del CSV fuera de estos
    # conjuntos es una que se borro en el dashboard, y el espejo la quita.
    prod_vivos = set(prod_nuevas)
    ofe_vivos = set(ofe_nuevas)
    pre_vivos = set(pre_nuevas)

    prod_fusion, n_prod, d_prod = _fusionar_productos(
        leer_csv(DATOS / "productos_canonicos.csv"), prod_nuevas
    )
    ofe_fusion, n_ofe, d_ofe = _fusionar(leer_csv(DATOS / "ofertas_tienda.csv"), ofe_nuevas, ofe_vivos)
    pre_fusion, n_pre, d_pre = _fusionar(leer_csv(DATOS / "precios_oferta.csv"), pre_nuevas, pre_vivos)
    proc_fusion, n_proc, d_proc = _fusionar_procedencia(
        leer_csv(DATOS / "productos_procedencia.csv"), proc_nuevas, prod_vivos
    )

    print("=== volcado base -> CSV ===")
    omitidos = len(ids_excluidos)
    print(
        f"  productos:   {len(prod_fusion):5} en CSV "
        f"(+{n_prod} nuevos, -{d_prod} borrados, {omitidos} no curados omitidos)"
    )
    print(f"  ofertas:     {len(ofe_fusion):5} en CSV (+{n_ofe} nuevas, -{d_ofe} borradas)")
    print(f"  precios:     {len(pre_fusion):5} en CSV (+{n_pre} nuevos, -{d_pre} borrados)")
    print(f"  procedencia: {len(proc_fusion):5} en CSV (+{n_proc} nuevas, -{d_proc} borradas)")

    if solo_ensayo:
        print("\nEnsayo. Sin --escribir no se toca ningun fichero.")
        return 0

    _guardar("productos_canonicos", COLUMNAS_PRODUCTO, prod_fusion, "sku_interno")
    _guardar("ofertas_tienda", COLUMNAS_OFERTA, ofe_fusion, "id")
    _guardar("precios_oferta", COLUMNAS_PRECIO, pre_fusion, "id")
    _guardar("productos_procedencia", COLUMNAS_PROCEDENCIA, proc_fusion, "sku_interno")
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
