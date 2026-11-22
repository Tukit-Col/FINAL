"""Carga los datos curados del catalogo a la base y dice que les falta.

Decisiones:
- La escritura es idempotente, por llave natural, y por capas: `concepto` (lo que pide el colegio),
  `producto_canonico` (la cosa identificable) y `oferta_tienda` con `precio_oferta` (lo que cada
  tienda cobra hoy).
- Un cargador no debe funcionar a medias en silencio: los valores por omision (un tipo de item
  asumido, `unidades_por_empaque` en 1) se reportan como carencia con su conteo en lugar de
  rellenarse a la callada.

Uso:  python -m tukit_catalogo.cargador [--solo-validar]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .extraccion import extraer_atributos


@dataclass(frozen=True)
class Problema:
    bloqueante: bool
    clase: str
    detalle: str

    def __str__(self) -> str:
        marca = "BLOQUEA" if self.bloqueante else "carencia"
        return f"[{marca}] {self.clase}: {self.detalle}"


def normalizar_isbn(crudo: str | None) -> str | None:
    if not crudo:
        return None
    limpio = re.sub(r"[^0-9Xx]", "", crudo).upper()
    return limpio or None


def ean13(crudo: str | None) -> str | None:
    digitos = re.sub(r"\D", "", crudo or "")
    if len(digitos) == 12:
        return "0" + digitos
    return digitos if len(digitos) == 13 else None


def isbn13_valido(crudo: str | None) -> bool:
    isbn = normalizar_isbn(crudo)
    if not isbn or len(isbn) != 13 or not isbn.isdigit():
        return False
    if not isbn.startswith(("978", "979")):
        return False
    suma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn[:12]))
    control = (10 - suma % 10) % 10
    return control == int(isbn[12])


def pesos_a_centavos(crudo: Any) -> int:
    if crudo is None:
        raise ValueError("precio vacio")
    texto = re.sub(r"[^0-9-]", "", str(crudo))
    if not texto:
        raise ValueError(f"precio sin digitos: {crudo!r}")
    pesos = int(texto)
    if pesos <= 0:
        raise ValueError(f"precio no positivo: {crudo!r}")
    return pesos * 100


def validar_referencias(
    *,
    conceptos: set[str],
    productos: dict[str, str],
    tiendas: set[str],
    ofertas: dict[str, tuple[str, str]],
    precios: dict[str, str],
) -> list[Problema]:
    problemas: list[Problema] = []

    for producto_id, concepto_id in productos.items():
        if concepto_id not in conceptos:
            problemas.append(
                Problema(True, "referencia", f"producto {producto_id} -> concepto {concepto_id}")
            )

    for oferta_id, (producto_id, tienda_id) in ofertas.items():
        if producto_id not in productos:
            problemas.append(Problema(True, "referencia", f"oferta {oferta_id} -> producto {producto_id}"))
        if tienda_id not in tiendas:
            problemas.append(Problema(True, "referencia", f"oferta {oferta_id} -> tienda {tienda_id}"))

    for precio_id, oferta_id in precios.items():
        if oferta_id not in ofertas:
            problemas.append(Problema(True, "referencia", f"precio {precio_id} -> oferta {oferta_id}"))

    return problemas


VERDADERO = frozenset({"true", "t", "1", "si", "yes", "verdadero"})


def _bool(crudo: str | None, *, por_omision: bool = False) -> bool:
    if crudo is None or not str(crudo).strip():
        return por_omision
    return str(crudo).strip().lower() in VERDADERO


def _texto(crudo: str | None) -> str | None:
    if crudo is None:
        return None
    limpio = crudo.strip()
    return limpio or None


def _lista(crudo: str | None) -> list[str]:
    limpio = (crudo or "").strip()
    if not limpio or limpio in ("[]", "{}"):
        return []
    if limpio.startswith("["):
        import json

        try:
            valor = json.loads(limpio)
            return [str(x) for x in valor] if isinstance(valor, list) else []
        except ValueError:
            return []
    separador = "|" if "|" in limpio else ","
    return [p.strip() for p in limpio.split(separador) if p.strip()]


def _fecha(crudo: str | None) -> datetime:
    limpio = (crudo or "").strip()
    if not limpio:
        return datetime.now(UTC)
    try:
        valor = datetime.fromisoformat(limpio)
    except ValueError:
        return datetime.now(UTC)
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


_ATRIBUTOS_LEGADO = frozenset({"cantidades_declaradas", "frase_ancla"})


def atributos_de_csv(crudo: str | None) -> dict[str, Any]:
    texto = (crudo or "").strip()
    if not texto:
        return {}
    try:
        valor = json.loads(texto)
    except json.JSONDecodeError:
        return {}
    if not isinstance(valor, dict):
        return {}
    return {k: v for k, v in valor.items() if k not in _ATRIBUTOS_LEGADO}


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Informe:
    escritos: dict[str, int]
    problemas: list[Problema]
    carencias: dict[str, tuple[int, int]]

    @property
    def bloqueado(self) -> bool:
        return any(p.bloqueante for p in self.problemas)

    def imprimir(self) -> None:
        print("\n=== cargado ===")
        for tabla, n in self.escritos.items():
            print(f"  {tabla:24} {n:5}")

        bloqueantes = [p for p in self.problemas if p.bloqueante]
        if bloqueantes:
            print(f"\n=== {len(bloqueantes)} problema(s) que BLOQUEAN ===")
            for p in bloqueantes[:20]:
                print(f"  {p}")
            if len(bloqueantes) > 20:
                print(f"  ... y {len(bloqueantes) - 20} mas")

        if self.carencias:
            print("\n=== lo que falta para poder mostrarlo a un papa ===")
            for que, (faltan, total) in sorted(self.carencias.items()):
                pct = 100 * faltan / total if total else 0
                print(f"  {que:38} {faltan:5}/{total:<5} ({pct:.0f}%)")

        otros = [p for p in self.problemas if not p.bloqueante]
        if otros:
            print(f"\n=== {len(otros)} carencia(s) con nombre propio ===")
            for p in otros[:15]:
                print(f"  {p}")
            if len(otros) > 15:
                print(f"  ... y {len(otros) - 15} mas")


CONCEPTOS_LIBRO = {
    "C034": ("Diccionario de espanol", ["diccionario", "diccionario de espanol", "dicc espanol"]),
    "C042": (
        "Constitucion Politica de Colombia",
        ["constitucion", "constitucion politica", "constitucion politica de colombia"],
    ),
    "C048": ("Biblia", ["biblia", "biblia catolica", "sagrada biblia"]),
    "C134": ("Libro o texto con título", ["plan lector", "libro plan lector", "plan lector libro"]),
}
CONCEPTOS_LIBRO_FUSIONADOS = {"dic-ingles": "C034"}


def _uuid_estable(*partes: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, "tukit:" + ":".join(partes))


AGENTE_FIRECRAWL = uuid.uuid5(uuid.NAMESPACE_URL, "tukit:agente:firecrawl")

COLUMNAS_ENRIQUECIDAS = frozenset(
    {"imagen_url", "atributos", "unidades_por_empaque", "unidad_base", "personaje"}
)


class Cargador:
    def __init__(self, directorio: Path) -> None:
        self.dir = directorio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}

    def armar(self) -> dict[str, list[dict[str, Any]]]:
        conceptos = self._conceptos()
        tiendas = self._tiendas()
        productos = self._productos(conceptos)
        ofertas, precios = self._ofertas(productos, tiendas)

        libros = self._libros(conceptos, tiendas)
        productos += libros["productos"]
        ofertas += libros["ofertas"]
        precios += libros["precios"]
        conceptos += libros["conceptos"]

        self.problemas += validar_referencias(
            conceptos={str(c["id"]) for c in conceptos},
            productos={str(p["id"]): str(p["concepto_id"]) for p in productos},
            tiendas={str(t["id"]) for t in tiendas},
            ofertas={str(o["id"]): (str(o["producto_canonico_id"]), str(o["tienda_id"])) for o in ofertas},
            precios={str(p["id"]): str(p["oferta_id"]) for p in precios},
        )
        self._medir_carencias(conceptos, productos, ofertas)

        return {
            "tienda": tiendas,
            "concepto": conceptos,
            "producto_canonico": productos,
            "oferta_tienda": ofertas,
            "precio_oferta": precios,
        }

    def _conceptos(self) -> list[dict[str, Any]]:
        filas = leer_csv(self.dir / "conceptos.csv")
        return [
            {
                "id": uuid.UUID(f["id"]),
                "codigo": f["codigo"],
                "nombre_canonico": f["nombre_canonico"],
                "sinonimos": _lista(f.get("sinonimos")),
                "categoria": f.get("categoria") or "otro",
                "tipo_item": f.get("tipo_item") or "util",
                "atributos_discriminantes": _lista(f.get("atributos_discriminantes")),
                "atributos_descriptivos": _lista(f.get("atributos_descriptivos")),
                "admite_personaje": _bool(f.get("admite_personaje")),
                "frecuencia_demanda": int(f.get("frecuencia_demanda") or 0),
                "activo": _bool(f.get("activo"), por_omision=True),
                "uno_por_estudiante": _bool(f.get("uno_por_estudiante")),
            }
            for f in filas
        ]

    def _tiendas(self) -> list[dict[str, Any]]:
        filas = leer_csv(self.dir / "tiendas.csv")
        tiendas = [
            {
                "id": uuid.UUID(f["id"]),
                "slug": f["slug"],
                "nombre": f["nombre"],
                "tipo": f.get("tipo") or "minorista",
                "url_base": _texto(f.get("url_base")),
                "activa": _bool(f.get("activa"), por_omision=True),
            }
            for f in filas
        ]
        conocidas = {t["slug"] for t in tiendas}
        for slug, nombre, url in (
            ("panamericana", "Panamericana", "https://www.panamericana.com.co"),
            ("librerianacional", "Libreria Nacional", "https://www.librerianacional.com"),
            ("buscalibre", "Buscalibre Colombia", "https://www.buscalibre.com.co"),
            ("tirant", "Tirant lo Blanch Colombia", "https://editorial.tirant.com/co"),
            ("edileyer", "Edileyer", "https://edileyer.com"),
        ):
            if slug not in conocidas:
                tiendas.append(
                    {
                        "id": _uuid_estable("tienda", slug),
                        "slug": slug,
                        "nombre": nombre,
                        "tipo": "minorista",
                        "url_base": url,
                        "activa": True,
                    }
                )
        return tiendas

    def _productos(self, conceptos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        del conceptos
        filas = leer_csv(self.dir / "productos_canonicos.csv")
        self.empaque_en_csv = bool(filas) and "unidades_por_empaque" in filas[0]
        productos = []
        for f in filas:
            ean = normalizar_isbn(f.get("ean"))
            productos.append(
                {
                    "id": uuid.UUID(f["id"]),
                    "concepto_id": uuid.UUID(f["concepto_id"]),
                    "ean": ean,
                    "sku_interno": _texto(f.get("sku_interno")),
                    "nombre": f["nombre"],
                    "descripcion": _texto(f.get("descripcion")),
                    "marca": _texto(f.get("marca")),
                    "nivel": f.get("nivel") or "confiable",
                    "personaje": _texto(f.get("personaje")),
                    "imagen_url": _texto(f.get("imagen_url")),
                    "atributos": atributos_de_csv(f.get("atributos")),
                    "ruta_categoria": _texto(f.get("ruta_categoria")),
                    "es_propio": _bool(f.get("es_propio")),
                    "es_representante_canonico": _bool(f.get("es_representante_canonico")),
                    "activo": _bool(f.get("activo"), por_omision=True),
                    "unidad_base": f.get("unidad_base") or "unidad",
                    "unidades_por_empaque": int(f.get("unidades_por_empaque") or 1),
                    "quality_score": float(f.get("quality_score") or 0.7),
                    "curado_por": uuid.UUID(f["curado_por"]),
                }
            )
        return productos

    def _ofertas(
        self, productos: list[dict[str, Any]], tiendas: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        del productos, tiendas
        ofertas = [
            {
                "id": uuid.UUID(f["id"]),
                "producto_canonico_id": uuid.UUID(f["producto_canonico_id"]),
                "tienda_id": uuid.UUID(f["tienda_id"]),
                "referencia_externa": _texto(f.get("referencia_externa")),
                "url": _texto(f.get("url")),
                "metodo_vinculacion": f.get("metodo_vinculacion") or "manual",
                "confianza_vinculacion": float(f.get("confianza_vinculacion") or 1.0),
                "disponible": _bool(f.get("disponible"), por_omision=True),
                "activo": _bool(f.get("activo"), por_omision=True),
            }
            for f in leer_csv(self.dir / "ofertas_tienda.csv")
        ]

        precios = []
        for f in leer_csv(self.dir / "precios_oferta.csv"):
            try:
                valor = int(f["valor_centavos"])
                if valor <= 0:
                    raise ValueError(f["valor_centavos"])
            except (KeyError, ValueError):
                self.problemas.append(
                    Problema(True, "precio", f"oferta {f.get('oferta_id')}: {f.get('valor_centavos')!r}")
                )
                continue
            precios.append(
                {
                    "id": uuid.UUID(f["id"]),
                    "oferta_id": uuid.UUID(f["oferta_id"]),
                    "valor_centavos": valor,
                    "moneda": f.get("moneda") or "COP",
                    "fuente": f.get("fuente") or "scraper",
                    "vigente_desde": _fecha(f.get("vigente_desde")),
                }
            )
        return ofertas, precios

    def _libros(
        self, conceptos: list[dict[str, Any]], tiendas: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        filas = leer_csv(self.dir / "libros_firecrawl.csv")
        if not filas:
            return {"conceptos": [], "productos": [], "ofertas": [], "precios": []}

        por_slug = {t["slug"]: t["id"] for t in tiendas}
        por_codigo = {c["codigo"]: c for c in conceptos}

        for f in filas:
            f["concepto_codigo"] = CONCEPTOS_LIBRO_FUSIONADOS.get(f["concepto_codigo"], f["concepto_codigo"])

        nuevos_conceptos = []
        demanda = defaultdict(int)
        for f in filas:
            demanda[f["concepto_codigo"]] += 1

        ids_concepto: dict[str, uuid.UUID] = {}
        for codigo, (nombre, sinonimos) in CONCEPTOS_LIBRO.items():
            existente = por_codigo.get(codigo)
            if existente is not None:
                ids_concepto[codigo] = existente["id"]
                existente["tipo_item"] = "libro_libre"
                continue
            ids_concepto[codigo] = _uuid_estable("concepto", codigo)
            nuevos_conceptos.append(
                {
                    "id": ids_concepto[codigo],
                    "codigo": codigo,
                    "nombre_canonico": nombre,
                    "sinonimos": sinonimos,
                    "categoria": "Diccionario / Biblia / Libros / Constitución",
                    "tipo_item": "libro_libre",
                    "atributos_discriminantes": [],
                    "atributos_descriptivos": [],
                    "uno_por_estudiante": True,
                    "admite_personaje": False,
                    "frecuencia_demanda": demanda[codigo],
                    "activo": True,
                }
            )

        productos: dict[str, dict[str, Any]] = {}
        ofertas: list[dict[str, Any]] = []
        precios: list[dict[str, Any]] = []
        discriminantes = {
            c["codigo"]: tuple(c.get("atributos_discriminantes") or ())
            for c in [*conceptos, *nuevos_conceptos]
        }

        niveles_por_isbn: dict[str, set[str]] = defaultdict(set)
        for f in filas:
            isbn_f = normalizar_isbn(f.get("isbn13"))
            if isbn_f:
                niveles_por_isbn[isbn_f].add(f.get("nivel") or "confiable")
        for isbn_f, vistos in niveles_por_isbn.items():
            if len(vistos) > 1:
                self.problemas.append(
                    Problema(
                        True,
                        "nivel",
                        f"el ISBN {isbn_f} se declara en dos niveles a la vez: {sorted(vistos)}",
                    )
                )

        for i, f in enumerate(filas):
            isbn = normalizar_isbn(f.get("isbn13"))
            if not isbn13_valido(isbn):
                self.problemas.append(
                    Problema(True, "isbn", f"fila {i + 2} de libros_firecrawl.csv: {f.get('isbn13')!r}")
                )
                continue

            if f["concepto_codigo"] not in ids_concepto:
                self.problemas.append(
                    Problema(True, "concepto", f"codigo desconocido: {f['concepto_codigo']}")
                )
                continue

            slug = f["tienda_slug"]
            if slug not in por_slug:
                self.problemas.append(Problema(True, "tienda", f"slug desconocido: {slug}"))
                continue

            if isbn not in productos:
                productos[isbn] = {
                    "id": _uuid_estable("libro", isbn),
                    "concepto_id": ids_concepto[f["concepto_codigo"]],
                    "ean": isbn,
                    "sku_interno": f"TK-LIB-{isbn}",
                    "nombre": f["titulo"],
                    "descripcion": None,
                    "marca": _texto(f.get("editorial")),
                    "nivel": f.get("nivel") or "confiable",
                    "personaje": None,
                    "imagen_url": _texto(f.get("imagen_url")),
                    "atributos": {
                        **extraer_atributos(f["titulo"], discriminantes.get(f["concepto_codigo"], ())),
                        **atributos_de_csv(f.get("atributos")),
                        "isbn13": isbn,
                    },
                    "ruta_categoria": "Libros",
                    "es_propio": False,
                    "es_representante_canonico": False,
                    "activo": True,
                    "unidad_base": "unidad",
                    "unidades_por_empaque": 1,
                    "quality_score": 0.9,
                    "curado_por": AGENTE_FIRECRAWL,
                }
            elif not productos[isbn]["imagen_url"] and _texto(f.get("imagen_url")):
                productos[isbn]["imagen_url"] = _texto(f["imagen_url"])

            oferta_id = _uuid_estable("oferta", isbn, slug)
            ofertas.append(
                {
                    "id": oferta_id,
                    "producto_canonico_id": productos[isbn]["id"],
                    "tienda_id": por_slug[slug],
                    "referencia_externa": _texto(f.get("sku_tienda")) or isbn,
                    "url": _texto(f.get("url_origen")),
                    "metodo_vinculacion": "ean",
                    "confianza_vinculacion": 1.0,
                    "disponible": _bool(f.get("disponible"), por_omision=True),
                    "activo": True,
                }
            )

            try:
                centavos = pesos_a_centavos(f.get("precio_cop"))
            except ValueError as error:
                self.problemas.append(Problema(True, "precio", f"{f['titulo'][:40]}: {error}"))
                continue

            precios.append(
                {
                    "id": _uuid_estable("precio", isbn, slug),
                    "oferta_id": oferta_id,
                    "valor_centavos": centavos,
                    "moneda": "COP",
                    "fuente": "scraper",
                    "vigente_desde": _fecha(f.get("observado_en")),
                }
            )

        return {
            "conceptos": nuevos_conceptos,
            "productos": list(productos.values()),
            "ofertas": ofertas,
            "precios": precios,
        }

    def _medir_carencias(
        self,
        conceptos: list[dict[str, Any]],
        productos: list[dict[str, Any]],
        ofertas: list[dict[str, Any]],
    ) -> None:
        total_p = len(productos)
        if total_p:
            self.carencias["productos sin imagen"] = (
                sum(1 for p in productos if not p["imagen_url"]),
                total_p,
            )
            self.carencias["productos sin atributos"] = (
                sum(1 for p in productos if not p["atributos"]),
                total_p,
            )
            self.carencias["productos sin marca"] = (
                sum(1 for p in productos if not p["marca"]),
                total_p,
            )
            self.carencias["productos con empaque asumido en 1"] = (
                sum(1 for p in productos if p["unidades_por_empaque"] == 1),
                total_p,
            )

        total_c = len(conceptos)
        if total_c:
            con_producto = {str(p["concepto_id"]) for p in productos}
            self.carencias["conceptos sin ningun producto"] = (
                sum(1 for c in conceptos if str(c["id"]) not in con_producto),
                total_c,
            )
            niveles = defaultdict(set)
            for p in productos:
                niveles[str(p["concepto_id"])].add(p["nivel"])
            self.carencias["conceptos sin los 3 niveles"] = (
                sum(1 for c in conceptos if len(niveles[str(c["id"])]) < 3),
                total_c,
            )

        total_o = len(ofertas)
        if total_o:
            self.carencias["ofertas sin enlace a la tienda"] = (
                sum(1 for o in ofertas if not o["url"]),
                total_o,
            )

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy import func, literal_column
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("catalogo")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                for tabla in ("tienda", "concepto", "producto_canonico", "oferta_tienda", "precio_oferta"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    if tabla == "producto_canonico":
                        await _liberar_skus(conexion, objeto, filas)
                    sentencia = insert(objeto).values(filas)
                    actualizables = {
                        c.name: sentencia.excluded[c.name]
                        for c in objeto.columns
                        if c.name not in [k.name for k in objeto.primary_key.columns]
                        and c.name in filas[0]
                        and not (tabla == "producto_canonico" and c.name in COLUMNAS_ENRIQUECIDAS)
                        and not (tabla == "concepto" and c.name == "admite_personaje")
                    }
                    if tabla == "producto_canonico":
                        vacio = literal_column("'{}'::jsonb")
                        actualizables["atributos"] = func.coalesce(
                            func.nullif(sentencia.excluded.atributos, vacio), objeto.c.atributos
                        )
                        actualizables["imagen_url"] = func.coalesce(
                            sentencia.excluded.imagen_url, objeto.c.imagen_url
                        )
                        actualizables["personaje"] = sentencia.excluded.personaje
                        if getattr(self, "empaque_en_csv", False):
                            for columna in ("unidades_por_empaque", "unidad_base"):
                                actualizables[columna] = sentencia.excluded[columna]
                    if actualizables:
                        sentencia = sentencia.on_conflict_do_update(
                            index_elements=[c.name for c in objeto.primary_key.columns],
                            set_=actualizables,
                        )
                    else:
                        sentencia = sentencia.on_conflict_do_nothing()
                    await conexion.execute(sentencia)
                    escritos[tabla] = len(filas)
        finally:
            await motor.cerrar()
        return escritos


async def _liberar_skus(conexion: Any, objeto: Any, filas: list[dict[str, Any]]) -> None:
    from sqlalchemy import String, cast, literal, select, update

    nuevos = {f["id"]: f["sku_interno"] for f in filas}
    actuales = await conexion.execute(
        select(objeto.c.id, objeto.c.sku_interno).where(objeto.c.id.in_(list(nuevos)))
    )
    mueven = [pid for pid, sku in actuales if sku != nuevos[pid]]
    if mueven:
        await conexion.execute(
            update(objeto)
            .where(objeto.c.id.in_(mueven))
            .values(sku_interno=literal("TMP-") + cast(objeto.c.id, String))
        )


async def medir_en_bd() -> dict[str, tuple[int, int]]:
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    text("""
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE p.imagen_url IS NULL) AS sin_imagen,
                       -- Lo que se cuenta es faltar un atributo que FILTRA, no
                       -- tener el diccionario vacio. Un aserrin cuyo concepto
                       -- no declara ningun discriminante no le falta nada, y
                       -- contarlo como carencia inflaba el numero con
                       -- productos que ya estaban completos.
                       count(*) FILTER (
                           WHERE EXISTS (
                               SELECT 1 FROM unnest(c.atributos_discriminantes) AS a(nombre)
                               WHERE NOT (p.atributos ? a.nombre)
                           )
                       ) AS sin_atributos,
                       count(*) FILTER (
                           WHERE p.unidades_por_empaque = 1
                           AND p.nombre ~* '(x ?[0-9]+ ?(und|uds?|unidades|hojas|colores)|paquete de [0-9]+)'
                       ) AS empaque_no_leido
                FROM producto_canonico p
                JOIN concepto c ON c.id = p.concepto_id
                WHERE p.activo
            """)
                )
            ).one()
            conceptos = (
                await conexion.execute(
                    text("""
                WITH c AS (
                    SELECT c.id, count(p.id) AS prods, count(DISTINCT p.nivel) AS niveles
                    FROM concepto c
                    LEFT JOIN producto_canonico p ON p.concepto_id = c.id AND p.activo
                    WHERE c.tipo_item <> 'no_comprar'
                    GROUP BY c.id
                )
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE prods = 0) AS sin_producto,
                       count(*) FILTER (WHERE niveles < 3) AS sin_tres_niveles
                FROM c
            """)
                )
            ).one()
    finally:
        await motor.cerrar()

    return {
        "productos sin imagen": (fila.sin_imagen, fila.total),
        "productos sin un atributo que filtra": (fila.sin_atributos, fila.total),
        "empaque anunciado en el nombre y no leido": (fila.empaque_no_leido, fila.total),
        "conceptos sin ningun producto": (conceptos.sin_producto, conceptos.total),
        "conceptos sin los 3 niveles": (conceptos.sin_tres_niveles, conceptos.total),
    }


async def _principal(directorio: Path, solo_validar: bool) -> int:
    cargador = Cargador(directorio)
    datos = cargador.armar()

    informe = Informe(
        escritos={t: len(f) for t, f in datos.items()},
        problemas=cargador.problemas,
        carencias=cargador.carencias,
    )

    if informe.bloqueado:
        print("No se escribio nada: hay referencias o identificadores rotos.")
        informe.imprimir()
        return 1

    if not solo_validar:
        informe.escritos = await cargador.escribir(datos)
        informe.carencias = await medir_en_bd()

    informe.imprimir()
    if solo_validar:
        print("\n(--solo-validar: las carencias son las de los CSV, no las de la base)")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--datos", type=Path, default=Path("datos/catalogo"))
    analizador.add_argument("--solo-validar", action="store_true")
    args = analizador.parse_args()

    directorio = args.datos
    if not directorio.exists():
        print(f"No existe el directorio de datos: {directorio}")
        return 2

    return asyncio.run(_principal(directorio, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
