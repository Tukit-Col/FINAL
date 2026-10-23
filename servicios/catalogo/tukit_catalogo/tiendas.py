"""Cliente de las tiendas: buscar productos y leer sus fichas.

Este modulo es la unica puerta del catalogo hacia afuera. Antes cada
herramienta abria la suya: `enriquecer` tenia su lector de fichas y
`completar` su buscador, con la misma cabecera de navegador copiada en los
dos. Tenerla una sola vez importa mas por lo que viene que por lo que hay: el
dia que haya que pasar a Playwright para una tienda que no publique API, se
cambia aqui dentro y las tres herramientas siguen igual.

Las tiendas no corren todas sobre lo mismo. Exito y Panamericana son VTEX;
Grancentral es Shopify. La diferencia muere aqui dentro: las dos se traducen a
`Oferta` y arriba nadie se entera.

VTEX publica dos endpoints publicos que resuelven todo lo que el catalogo
necesita:

    /api/catalog_system/pub/products/search/<slug>/p   una ficha exacta
    /api/catalog_system/pub/products/search?ft=<texto> una busqueda

Shopify no tiene el segundo: no expone busqueda por relevancia. Publica el
catalogo entero en `/products.json`, de 250 en 250, y el filtro corre en casa.
Resulto ser mejor y no peor. El ranking de VTEX ante `lentejuelas` devuelve
veinticuatro renos con traje de lentejuelas y ni un paquete de lentejuelas, y
con eso las dimos por inexistentes durante semanas; filtrando en casa por
todas las palabras aparecen a $5.750.

La diferencia entre los dos endpoints de VTEX es la que separa un dato
confiable de una adivinanza, y por eso estan en funciones distintas con nombres distintos. La
ficha devuelve EL producto de esa direccion. La busqueda devuelve lo que se
parece al texto, que sirve para proponerle candidatos a una persona y no para
escribir en el catalogo sin que nadie mire.

Todo lo que se descarga queda en un cache en disco. No es para ir mas rapido,
aunque tambien: es para que el catalogo sea reproducible. Leer las fichas de
todo el catalogo toma tres minutos y depende de que las tiendas respondan
hoy igual que ayer. Con el cache versionado al lado de los CSV, cualquiera
puede reconstruir la base sin red y ver de que respuesta concreta salio cada
precio y cada foto.
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

# slug de tienda -> dominio. El slug es el que usa la base.
DOMINIOS = {
    "exito": "www.exito.com",
    "panamericana": "www.panamericana.com.co",
    "grancentral": "pgrancentral.com",
}

# Grancentral corre sobre Shopify, no sobre VTEX. Estuvo meses en la base
# marcada como "dominio caido" y no estaba caida: teniamos guardado
# `papeleriagrancentral.com`. Mientras el dominio estuvo mal, el catalogo se
# surtio de dos tiendas creyendo que eran tres, y por eso dimos por
# inexistentes las lentejuelas, los reforzadores y la tabla de picado, que
# Grancentral vende y las otras dos no.
SHOPIFY = frozenset({"grancentral"})

CACHE = Path(__file__).resolve().parents[3] / "datos" / "catalogo" / "cache_tiendas"


@dataclass(frozen=True)
class Oferta:
    """Lo que una tienda dice de un producto, en los terminos del catalogo."""

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
    """Trae un JSON de la tienda, con cache en disco y reintento.

    El reintento no es precaucion de manual. La primera version lanzaba varias
    consultas a la vez y las tiendas devolvian vacio a casi todas; parecia que
    no tenian el producto y lo que pasaba es que estaban limitando el ritmo.
    Un vacio por exceso de prisa se lee igual que un hueco real del catalogo,
    que es el peor modo de fallar para estas herramientas.
    """
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
            # VTEX responde con una lista de productos y Shopify con un objeto
            # que la envuelve. Lo que no se guarda es la respuesta vacia, que
            # es la que no distingue "no tiene" de "no contesto".
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
                    # Sin `encoding`, Windows escribe en cp1252: el primer
                    # nombre con un caracter fuera de esa tabla hacia fallar la
                    # escritura, el `except` lo tomaba por un fallo de red, y
                    # Grancentral devolvia siempre una lista vacia. Parecia que
                    # no tenia los productos.
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
    """Saca (dominio, slug) de la direccion de una ficha, o None si no lo es."""
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
    """El producto que vive en esa direccion. Exacto o nada.

    Se exige que la respuesta traiga UN producto. Si trae varios ya no es una
    ficha y no hay forma de saber cual era, asi que se devuelve None. Esa
    severidad es deliberada: ponerle a un producto la foto o el precio de otro
    parecido es peor que dejarlo vacio, porque el papa reconoce la imagen,
    pide confiado y recibe otra cosa. Sin dato al menos lee el nombre.
    """
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
    """Lo que la tienda cree que se parece al texto.

    Devuelve candidatos, no respuestas. Nada de aqui deberia entrar al
    catalogo sin que una persona lo mire: `punzon punta metalica` devuelve
    lapices correctores de punta fina, y son productos reales, con foto, con
    existencias y al precio esperado. Lo que falla es el significado, y eso no
    lo atrapa ningun umbral.
    """
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
    """Si el titulo contiene todas las palabras de la consulta.

    Shopify no tiene endpoint de busqueda por relevancia, asi que el filtro lo
    pone el catalogo. Lejos de ser una carencia, es lo que hizo aparecer
    productos que llevabamos por inexistentes: el buscador de Panamericana
    ordena por parecido y ante `lentejuelas` devuelve veinticuatro adornos
    navidenos con traje de lentejuelas antes que un paquete de lentejuelas,
    porque cada uno tiene la palabra. Exigir TODAS las palabras, cada una
    completa, decide por significado en vez de por ranking ajeno.
    """
    plano = _sin_tildes(titulo)
    palabras = _sin_tildes(consulta).split()
    return bool(palabras) and all(re.search(rf"\b{re.escape(p)}\b", plano) for p in palabras)


def _catalogo_shopify(tienda: str, dominio: str, paginas: int = 12) -> list[dict[str, Any]]:
    """El catalogo completo de la tienda, que Shopify publica sin llave.

    Se baja entero, de 250 en 250, y queda en el cache. Son 2.750 productos en
    Grancentral, once peticiones: mas barato que una consulta por concepto y
    ademas permite buscar sin red una vez bajado.
    """
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
    """Traduce un producto de Shopify a la `Oferta` que el catalogo entiende.

    Arriba de esta funcion nadie sabe que Grancentral corre sobre otra
    plataforma, y asi debe quedar: el enriquecedor y el cargador tratan las
    tres tiendas igual.
    """
    variantes = crudo.get("variants") or []
    if not variantes:
        return None

    # Grancentral es mayorista de San Victorino y publica cada cosa en dos
    # presentaciones, 'Unidad' y 'Docena', como variantes del mismo producto.
    # La tabla de picado vale $9.500 suelta y $94.200 por docena. Quien arma un
    # kit escolar necesita una, y ningun umbral de precio distingue: los dos
    # precios son correctos y del mismo producto. Solo lo dice la palabra.
    elegida = next(
        (v for v in variantes if str(v.get("option1") or "").strip().lower() == "unidad"),
        variantes[0],
    )

    imagenes = crudo.get("images") or []
    # El peso no tiene centavos en la practica y Shopify manda '5750.00'. Se
    # trunca en vez de redondear para que ningun '.99' suba el precio un peso
    # sin que nadie lo haya decidido.
    try:
        precio = int(float(elegida.get("price") or 0))
    except (TypeError, ValueError):
        return None

    # El sku viene vacio en casi todo el catalogo de Grancentral, y la base
    # necesita una referencia estable para no duplicar la oferta. El id de la
    # variante sirve: es de la tienda, no cambia y separa unidad de docena.
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
    # Un articulo por producto. Las variantes de color de un mismo cuaderno no
    # son opciones distintas para el kit: son el mismo cuaderno.
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
        # VTEX devuelve cero cuando el articulo no se vende en linea, y un
        # cero se propaga al total del kit como si fuera gratis.
        precio_cop=int(comercial.get("Price") or 0),
        disponible=(comercial.get("AvailableQuantity") or 0) > 0,
        imagen_url=imagenes[0].get("imageUrl") if imagenes else None,
        url=crudo.get("link") or "",
        sku=str(articulo.get("itemId") or ""),
        ean=ean if ean and ean.isdigit() and len(ean) in (8, 12, 13) else None,
        marca=(crudo.get("brand") or "").strip() or None,
        especificaciones=especificaciones,
    )
