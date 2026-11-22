"""Vuelca de la base a los CSV curados, para que el CSV reproduzca el catalogo.

Decisiones:
- Invariante de ida y vuelta: tras `bd-cargar && bd-completar && bd-volcar`, una segunda
  `bd-cargar` sobre una base limpia reproduce el mismo estado.
- La base manda sobre que filas existen y el CSV sobre como se ven: una fila borrada de la base se
  elimina del CSV, una que sigue se conserva tal cual (el CSV es dueno de `nivel`, `atributos` y de
  los arreglos manuales) y las nuevas se agregan serializadas desde la base.
- Solo se vuelca lo curado: no los libros `TK-LIB-*` (los sintetiza el cargador) ni las sugerencias
  de maquina `TK-SUG-*` y `TMP-*`, que pertenecen a la cola `propuesta_producto` hasta que alguien
  las apruebe.
- Orden estable por `sku_interno` o `id`: dos volcados de la misma base dan el mismo archivo.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any

from .cargador import AGENTE_FIRECRAWL, leer_csv

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

PREFIJOS_NO_CURADOS = ("TK-LIB-", "TK-SUG-", "TMP-")


def _es_curado(sku: str | None, curado_por: Any) -> bool:
    sku = sku or ""
    if sku.startswith("TK-REV-"):
        return True
    if sku.startswith(PREFIJOS_NO_CURADOS):
        return False
    return str(curado_por) != str(AGENTE_FIRECRAWL)


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
    "unidad_base",
    "unidades_por_empaque",
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

FUENTE_COLA = "cola_revision"


def _s(valor: Any) -> str:
    return "" if valor is None else str(valor)


def _bool_csv(valor: Any) -> str:
    if valor is None:
        return ""
    return "true" if valor else "false"


def _num3(valor: Any) -> str:
    return "" if valor is None else f"{float(valor):.3f}"


def _fecha_csv(valor: Any) -> str:
    return "" if valor is None else valor.isoformat()


def _atributos_csv(valor: Any) -> str:
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
        "unidad_base": _s(p.unidad_base),
        "unidades_por_empaque": _s(p.unidades_por_empaque),
        "ruta_categoria": _s(p.ruta_categoria),
        "es_propio": _bool_csv(p.es_propio),
        "grupo_variante_id": _s(p.grupo_variante_id),
        "es_representante_canonico": _bool_csv(p.es_representante_canonico),
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


COLUMNAS_PROPIAS_DEL_CSV = frozenset({"quality_score"})


def _fusionar(
    existentes: list[dict[str, str]],
    nuevas_por_id: dict[str, dict[str, str]],
    ids_vivos: set[str],
) -> tuple[list[dict[str, str]], int, int]:
    conservadas = [fila for fila in existentes if fila["id"] in ids_vivos]
    eliminadas = len(existentes) - len(conservadas)
    vistos = {fila["id"] for fila in conservadas}
    agregadas = [fila for id_, fila in nuevas_por_id.items() if id_ not in vistos]
    return conservadas + agregadas, len(agregadas), eliminadas


def _fusionar_productos(
    existentes: list[dict[str, str]],
    nuevas_por_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], int, int]:
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
    conservadas = [fila for fila in existentes if fila["producto_id"] in productos_vivos]
    eliminadas = len(existentes) - len(conservadas)
    for fila in conservadas:
        nueva = nuevas_por_producto.get(fila["producto_id"])
        if nueva is not None:
            fila["sku_interno"] = nueva["sku_interno"]
    vistos = {fila["producto_id"] for fila in conservadas}
    agregadas = [fila for pid, fila in nuevas_por_producto.items() if pid not in vistos]
    return conservadas + agregadas, len(agregadas), eliminadas


def _guardar(nombre: str, columnas: list[str], filas: list[dict[str, str]], clave: str) -> None:
    ruta = DATOS / f"{nombre}.csv"
    ordenadas = sorted(filas, key=lambda f: f[clave])
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(ordenadas)


async def _leer_base() -> dict[str, list[Any]]:
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
