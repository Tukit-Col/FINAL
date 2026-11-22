"""Cliente de las tiendas: buscar productos y leer sus fichas.

Decisiones:
- Es la unica puerta del catalogo hacia afuera: las herramientas no abren la suya, y cambiar de
  tecnica para una tienda (por ejemplo a un navegador automatizado) se hace solo aqui.
- Exito y Panamericana son VTEX y Grancentral es Shopify; la diferencia se resuelve aqui dentro y
  ambas se traducen a `Oferta`.
- Shopify no expone busqueda por relevancia: se lee `/products.json` completo, de 250 en 250, y el
  filtro corre en casa.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

DOMINIOS = {
    "exito": "www.exito.com",
    "panamericana": "www.panamericana.com.co",
    "grancentral": "pgrancentral.com",
}

SHOPIFY = frozenset({"grancentral"})

CACHE = Path(__file__).resolve().parents[3] / "datos" / "catalogo" / "cache_tiendas"


@dataclass(frozen=True)
class Oferta:

    tienda: str
    nombre: str
    precio_cop: int
    disponible: bool
    imagen_url: str | None
    url: str
    sku: str
    ean: str | None
    marca: str | None
    especificaciones: dict[str, str]


def _pedir(direccion: str, clave_cache: str, dias_frescura: int = 7) -> Any | None:
    archivo = CACHE / f"{clave_cache}.json"
    if archivo.exists():
        edad = (datetime.now(UTC).timestamp() - archivo.stat().st_mtime) / 86400
        if edad < dias_frescura:
            try:
                return json.loads(archivo.read_text(encoding="utf-8"))["respuesta"]
            except (ValueError, KeyError):
                pass

    for intento in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(direccion, headers=CABECERAS), timeout=25
            ) as respuesta:
                datos = json.loads(respuesta.read())
            if datos and isinstance(datos, list | dict):
                CACHE.mkdir(parents=True, exist_ok=True)
                archivo.write_text(
                    json.dumps(
                        {
                            "url": direccion,
                            "leido_en": datetime.now(UTC).isoformat(),
                            "respuesta": datos,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return datos
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        if intento < 2:
            time.sleep(1.5 * (intento + 1))
    return None


def _clave(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower())[:120].strip("-")


def slug_de_url(url: str) -> tuple[str, str] | None:
    try:
        partes = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if not partes.hostname:
        return None
    ruta = partes.path.rstrip("/")
    if not ruta.endswith("/p"):
        return None
    slug = ruta[:-2].strip("/").split("/")[-1]
    return (partes.hostname, slug) if slug else None


def ficha(url: str) -> Oferta | None:
    partido = slug_de_url(url)
    if partido is None:
        return None
    dominio, slug = partido

    direccion = f"https://{dominio}/api/catalog_system/pub/products/search/{urllib.parse.quote(slug)}/p"
    datos = _pedir(direccion, f"ficha-{_clave(dominio)}-{_clave(slug)}")
    if not datos or len(datos) != 1:
        return None

    tienda = next((s for s, d in DOMINIOS.items() if d == dominio), dominio)
    return _a_oferta(tienda, datos[0])


def buscar(tienda: str, consulta: str, cuantos: int = 24) -> list[Oferta]:
    dominio = DOMINIOS.get(tienda)
    if dominio is None:
        return []
    if tienda in SHOPIFY:
        return _buscar_shopify(tienda, dominio, consulta, cuantos)
    direccion = (
        f"https://{dominio}/api/catalog_system/pub/products/search"
        f"?ft={urllib.parse.quote(consulta)}&_from=0&_to={cuantos - 1}"
    )
    datos = _pedir(direccion, f"busca-{tienda}-{_clave(consulta)}", dias_frescura=3)
    if not datos:
        return []
    return [o for crudo in datos if (o := _a_oferta(tienda, crudo)) is not None]


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _coincide(titulo: str, consulta: str) -> bool:
    plano = _sin_tildes(titulo)
    palabras = _sin_tildes(consulta).split()
    return bool(palabras) and all(re.search(rf"\b{re.escape(p)}\b", plano) for p in palabras)


def _catalogo_shopify(tienda: str, dominio: str, paginas: int = 12) -> list[dict[str, Any]]:
    todo: list[dict[str, Any]] = []
    for pagina in range(1, paginas + 1):
        datos = _pedir(
            f"https://{dominio}/products.json?limit=250&page={pagina}",
            f"shopify-{tienda}-p{pagina}",
            dias_frescura=3,
        )
        lote = (datos or {}).get("products") or [] if isinstance(datos, dict) else []
        if not lote:
            break
        todo.extend(lote)
    return todo


def _buscar_shopify(tienda: str, dominio: str, consulta: str, cuantos: int) -> list[Oferta]:
    encontradas = []
    for crudo in _catalogo_shopify(tienda, dominio):
        if not _coincide(crudo.get("title") or "", consulta):
            continue
        if (oferta := _a_oferta_shopify(tienda, dominio, crudo)) is not None:
            encontradas.append(oferta)
        if len(encontradas) >= cuantos:
            break
    return encontradas


def _a_oferta_shopify(tienda: str, dominio: str, crudo: dict[str, Any]) -> Oferta | None:
    variantes = crudo.get("variants") or []
    if not variantes:
        return None

    elegida = next(
        (v for v in variantes if str(v.get("option1") or "").strip().lower() == "unidad"),
        variantes[0],
    )

    imagenes = crudo.get("images") or []
    try:
        precio = int(float(elegida.get("price") or 0))
    except (TypeError, ValueError):
        return None

    referencia = str(elegida.get("sku") or "").strip() or str(elegida.get("id") or "")

    return Oferta(
        tienda=tienda,
        nombre=(crudo.get("title") or "").strip(),
        precio_cop=precio,
        disponible=bool(elegida.get("available")),
        imagen_url=(imagenes[0].get("src") if imagenes else None),
        url=f"https://{dominio}/products/{crudo.get('handle') or ''}",
        sku=referencia,
        ean=None,
        marca=(crudo.get("vendor") or "").strip() or None,
        especificaciones={},
    )


def _a_oferta(tienda: str, crudo: dict[str, Any]) -> Oferta | None:
    articulos = crudo.get("items") or []
    if not articulos:
        return None
    articulo = articulos[0]

    vendedores = articulo.get("sellers") or []
    comercial = (vendedores[0].get("commertialOffer") or {}) if vendedores else {}
    imagenes = articulo.get("images") or []

    especificaciones: dict[str, str] = {}
    for nombre in crudo.get("allSpecifications") or []:
        valores = crudo.get(nombre) or []
        if valores and valores[0]:
            especificaciones[nombre] = str(valores[0]).strip()

    ean = (articulo.get("ean") or "").strip() or None
    return Oferta(
        tienda=tienda,
        nombre=(crudo.get("productName") or articulo.get("name") or "").strip(),
        precio_cop=int(comercial.get("Price") or 0),
        disponible=(comercial.get("AvailableQuantity") or 0) > 0,
        imagen_url=imagenes[0].get("imageUrl") if imagenes else None,
        url=crudo.get("link") or "",
        sku=str(articulo.get("itemId") or ""),
        ean=ean if ean and ean.isdigit() and len(ean) in (8, 12, 13) else None,
        marca=(crudo.get("brand") or "").strip() or None,
        especificaciones=especificaciones,
    )
