"""Convierte los CSV del catalogo y el corpus de listas en semillas JSON.

El origen simulado del frontend no inventa datos: los lee de los mismos
ficheros que alimentan la base. Asi lo que la usuaria ve en pantalla hoy es lo
que el backend va a devolver manana, y una diferencia entre los dos es un
defecto visible en vez de una sorpresa el dia del cambio de bandera.

Se ejecuta a mano y su salida se versiona, para que `npm install` no dependa
de Python:

    python3 libs/ts/tukit-contrato/herramientas/generar_semillas.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RAIZ_MONOREPO = Path(__file__).resolve().parents[4]
RAIZ_TRABAJO = RAIZ_MONOREPO.parent
DATOS_CATALOGO = RAIZ_MONOREPO / "datos" / "catalogo"
CORPUS = RAIZ_TRABAJO / "Arquitectura" / "Corpus_ItemLista_v2.csv"
SALIDA = Path(__file__).resolve().parents[1] / "src" / "simulado"

# El corpus identifica los colegios por el codigo con que se transcribieron
# (`2.4` es el que usa el ejemplo del CONTRATO_API), no por nombre. Los
# nombres salen del encabezado del PDF de cada uno, cuando el PDF lo dice.
#
# `2.8` y `2.9` comparten plantilla y la extraccion no los pudo separar con
# confianza: son los dos PDF con 115 renglones en juego que el CONTRATO_API
# §2.2 marca como bloqueante de la ruta "elegir colegio y grado". Por eso
# van con `atribucion_dudosa` y la UI lo dice en vez de callarlo.
NOMBRES_COLEGIO: dict[str, dict[str, Any]] = {
    "1.1": {"nombre": "Colegio 1.1", "fuente": "Listas_Utiles_Consolidado.xlsx"},
    "1.2": {"nombre": "Colegio 1.2", "fuente": "Listas_Utiles_Consolidado.xlsx"},
    "1.3": {"nombre": "Colegio 1.3", "fuente": "Listas_Utiles_Consolidado.xlsx"},
    "2.1": {"nombre": "Colegio 2.1", "fuente": "matilde.pdf"},
    "2.2": {
        "nombre": "Colegio Parroquial Nuestra Senora del Rosario",
        "fuente": "LISTA-DE-TEXTOS-Y-UTILES-2021.pdf",
    },
    "2.3": {
        "nombre": "Colegio Parroquial San Jose de Fontibon",
        "fuente": "LISTAS-DE-TEXTOS-ESCOLARES-COLEGIO-SAN-JOSE-DE-FONTIBON.pdf",
    },
    "2.4": {"nombre": "Colegio San Pedro Claver", "fuente": "san pedro.pdf"},
    "2.5": {"nombre": "Colegio 2.5", "fuente": "LISTA-DE-UTILES-2026.pdf"},
    "2.6": {"nombre": "Colegio Santa Teresa de Jesus", "fuente": "JARDIN_merged.pdf"},
    "2.7": {"nombre": "Colegio 2.7", "fuente": "LISTAS-TEXTOS-UTILES-2026.pdf"},
    "2.8": {
        "nombre": "Gimnasio Modelia Real",
        "fuente": "LISTAS-DE-UTILES-2025-ACT.pdf",
        "atribucion_dudosa": True,
    },
    "2.9": {"nombre": "Colegio 2.9", "fuente": "modelia.pdf", "atribucion_dudosa": True},
    "2.10": {"nombre": "Jardin Osito de Miel", "fuente": "ositodemiel.pdf"},
    "2.11": {"nombre": "Colegio 2.11", "fuente": "bahiasolano.pdf"},
    "2.12": {"nombre": "Unidad Educativa Prados de Alameda", "fuente": "alamei.pdf"},
    "2.13": {
        "nombre": "Colegio Agustiniano Ciudad Salitre",
        "fuente": "TEXTOS-Y-UTILES-ESCOLARES-2026-CACS.pdf",
    },
    "2.14": {"nombre": "Colegio 2.14", "fuente": "Listas 2026.pdf"},
}

# El orden en que un colegio ordena sus grados, para no listarlos alfabeticos.
ORDEN_GRADOS = [
    "Parvulos",
    "Prejardin",
    "Jardin",
    "Transicion",
    "Primero",
    "Segundo",
    "Tercero",
    "Cuarto",
    "Quinto",
    "Sexto",
    "Septimo",
    "Octavo",
    "Noveno",
    "Decimo",
    "Once",
]


def _filas(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _lista_texto(crudo: str) -> list[str]:
    return [t for t in (crudo or "").split("|") if t]


def _json_o_vacio(crudo: str) -> dict[str, Any]:
    if not crudo:
        return {}
    try:
        valor = json.loads(crudo)
    except json.JSONDecodeError:
        return {}
    return valor if isinstance(valor, dict) else {}


def semilla_catalogo() -> dict[str, Any]:
    tiendas_por_id = {
        f["id"]: {
            "slug": f["slug"],
            "nombre": f["nombre"],
            "tipo": f["tipo"],
            "url_base": f["url_base"] or None,
        }
        for f in _filas(DATOS_CATALOGO / "tiendas.csv")
        if f["activa"].lower() == "true"
    }

    # El precio vigente es el tramo sin `vigente_hasta`. Es la misma
    # definicion que la restriccion de exclusion de `precio_oferta`.
    precio_por_oferta: dict[str, int] = {}
    for f in _filas(DATOS_CATALOGO / "precios_oferta.csv"):
        if f["vigente_hasta"]:
            continue
        # La base guarda centavos; el CONTRATO_API habla de pesos enteros.
        # La conversion se hace aqui, una sola vez, y no en la vista.
        precio_por_oferta[f["oferta_id"]] = int(f["valor_centavos"]) // 100

    ofertas_por_producto: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in _filas(DATOS_CATALOGO / "ofertas_tienda.csv"):
        if f["activo"].lower() != "true":
            continue
        tienda = tiendas_por_id.get(f["tienda_id"])
        if tienda is None:
            continue
        disponible = f["disponible"]
        ofertas_por_producto[f["producto_canonico_id"]].append(
            {
                "tienda": tienda["slug"],
                "tienda_nombre": tienda["nombre"],
                "precio": precio_por_oferta.get(f["id"]),
                "url": f["url"] or None,
                # Tres valores: `null` es "no se observo", no "no hay".
                "disponible": None if disponible == "" else disponible.lower() == "true",
                "visto_en": f["visto_en"] or None,
                "confianza_vinculacion": float(f["confianza_vinculacion"]),
            }
        )
    for ofertas in ofertas_por_producto.values():
        ofertas.sort(key=lambda o: (o["precio"] is None, o["precio"] or 0))

    productos_por_concepto: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in _filas(DATOS_CATALOGO / "productos_canonicos.csv"):
        if f["activo"].lower() != "true":
            continue
        productos_por_concepto[f["concepto_id"]].append(
            {
                "sku": f["sku_interno"],
                "ean": f["ean"] or None,
                "nombre": f["nombre"],
                "descripcion": f["descripcion"] or None,
                "marca": f["marca"] or None,
                "nivel": f["nivel"],
                "personaje": f["personaje"] or None,
                "imagen_url": f["imagen_url"] or None,
                "atributos": _json_o_vacio(f["atributos"]),
                "quality_score": float(f["quality_score"]),
                "es_propio": f["es_propio"].lower() == "true",
                "ofertas": ofertas_por_producto.get(f["id"], []),
            }
        )

    orden_nivel = {"economico": 0, "confiable": 1, "premium": 2}
    conceptos: list[dict[str, Any]] = []
    for f in _filas(DATOS_CATALOGO / "conceptos.csv"):
        if f["activo"].lower() != "true":
            continue
        productos = sorted(
            productos_por_concepto.get(f["id"], []),
            key=lambda p: (orden_nivel.get(p["nivel"], 9), p["nombre"]),
        )
        conceptos.append(
            {
                "codigo": f["codigo"],
                "nombre_canonico": f["nombre_canonico"],
                # Los sinonimos del corpus llegan a pasar de 70 por concepto y
                # en pantalla solo sirven los primeros: la lista completa
                # cuadruplicaba el peso del fichero sin decir nada mas.
                "sinonimos": _lista_texto(f["sinonimos"])[:12],
                "categoria": f["categoria"],
                "tipo_item": f["tipo_item"],
                "atributos_discriminantes": _lista_texto(f["atributos_discriminantes"]),
                "atributos_descriptivos": _lista_texto(f["atributos_descriptivos"]),
                "admite_personaje": f["admite_personaje"].lower() == "true",
                "frecuencia_demanda": int(f["frecuencia_demanda"]),
                "productos": productos,
            }
        )

    conceptos.sort(key=lambda c: (-c["frecuencia_demanda"], c["codigo"]))

    todos = [p for c in conceptos for p in c["productos"]]
    resumen = {
        "conceptos": len(conceptos),
        "productos": len(todos),
        "conceptos_con_tres_niveles": sum(
            1 for c in conceptos if len({p["nivel"] for p in c["productos"]}) >= 3
        ),
        "conceptos_sin_producto": sum(1 for c in conceptos if not c["productos"]),
        "productos_con_foto": sum(1 for p in todos if p["imagen_url"]),
        "tiendas": len(tiendas_por_id),
        "productos_sin_revisar": sum(1 for p in todos if p["quality_score"] < 0.5),
    }

    return {
        "resumen": resumen,
        "tiendas": sorted(tiendas_por_id.values(), key=lambda t: t["nombre"]),
        "conceptos": conceptos,
    }


def semilla_listas() -> dict[str, Any]:
    por_colegio_grado: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for f in _filas(CORPUS):
        clave = (f["colegio_id"], f["grado"])
        orden = len(por_colegio_grado[clave]) + 1
        item: dict[str, Any] = {
            "orden": orden,
            "texto_original": f["texto_original"],
            "texto_generico": f["texto_generico"] or None,
            "cantidad": max(1, int(f["cantidad"] or 1)),
            "categoria": f["categoria"] or None,
            "tipo_item": f["tipo_item"] or "util",
            # El corpus escribe `desconocido` donde el PDF no declara nada.
            # El CONTRATO_API no tiene ese valor, y el caso sin restriccion
            # declarada es justo `mercado_abierto`.
            "modo_adquisicion": (
                "mercado_abierto" if f["modo_adquisicion"] in ("", "desconocido") else f["modo_adquisicion"]
            ),
        }
        if f["libro_titulo"]:
            item["libro"] = {
                "titulo": f["libro_titulo"],
                "autor": f["libro_autor"] or None,
                "editorial": f["libro_editorial"] or None,
                "periodo": f["libro_periodo"] or None,
            }
        por_colegio_grado[clave].append(item)

    colegios: list[dict[str, Any]] = []
    for colegio_id in sorted(NOMBRES_COLEGIO, key=lambda s: [int(p) for p in s.split(".")]):
        grados = [g for (c, g) in por_colegio_grado if c == colegio_id]
        if not grados:
            continue
        meta = NOMBRES_COLEGIO[colegio_id]
        colegios.append(
            {
                "colegio_id": colegio_id,
                "nombre": meta["nombre"],
                "fuente": meta["fuente"],
                "atribucion_dudosa": bool(meta.get("atribucion_dudosa")),
                "grados": sorted(
                    set(grados),
                    key=lambda g: ORDEN_GRADOS.index(g) if g in ORDEN_GRADOS else 99,
                ),
            }
        )

    listas = [
        {
            "colegio_id": colegio_id,
            "grado": grado,
            "anio_lectivo": 2026,
            "version": 1,
            "items": items,
        }
        for (colegio_id, grado), items in sorted(por_colegio_grado.items())
    ]

    return {"colegios": colegios, "listas": listas}


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, datos in (
        ("semilla-catalogo.json", semilla_catalogo()),
        ("semilla-listas.json", semilla_listas()),
    ):
        destino = SALIDA / nombre
        destino.write_text(
            json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"{destino.relative_to(RAIZ_MONOREPO)}  {destino.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
