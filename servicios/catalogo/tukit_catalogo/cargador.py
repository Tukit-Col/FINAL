"""Carga los datos curados del catalogo a la base, y dice que les falta.

Esta es la pieza que cierra el hueco de fondo: habia un catalogo curado en
CSV y una base con el esquema correcto, y nada que llevara el uno a la otra.
Mientras eso siguio asi, el emparejamiento se probaba contra una tabla plana
donde `precio` era columna del producto, asi que comparar dos tiendas era
imposible por construccion.

El cargador tiene DOS trabajos, y el segundo es el que importa mas:

1. Escribir. Idempotente, por llave natural, para poder correrlo otra vez sin
   duplicar nada. Se carga por capas porque las tres capas existen por una
   razon: `concepto` es lo que el colegio pide, `producto_canonico` es la cosa
   identificable, y `oferta_tienda` mas `precio_oferta` son lo que cada tienda
   cobra por ella hoy.

2. Decir la verdad sobre lo que cargo. Un cargador que solo dice "listo, 242
   productos" es peor que ninguno, porque el problema real no es que falle:
   es que **funcione a medias en silencio**. Un producto sin imagen se carga
   igual de bien que uno con imagen, y el papa se entera al ver un hueco gris
   donde deberia ir un cuaderno.

Sobre los valores por omision, que son la trampa de este modelo. Casi toda
columna que los CSV no traen tiene un default razonable, y por eso mismo el
dato malo entra sin ruido:

- `concepto.tipo_item` cae en `util`. Un diccionario o una biblia entrarian
  clasificados como utiles, y el pipeline les buscaria papeleria.
- `producto_canonico.unidades_por_empaque` cae en 1. Para un libro esta bien;
  para una caja de doce colores es falso, y es precisamente el numero del que
  depende no sumar doce lapices al carrito cuando el colegio pidio una caja.

Ninguno de los dos se rellena a la callada: se reportan como carencia con su
conteo, para que se vea cuanto del catalogo esta apoyado en un default.

Uso:

    python -m tukit_catalogo.cargador                 # carga y reporta
    python -m tukit_catalogo.cargador --solo-validar  # no escribe nada
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

from .enriquecer import extraer_atributos

# ---------------------------------------------------------------------------
# Piezas puras. Sin base de datos, sin lectura de ficheros: es lo que las
# pruebas fijan, porque es donde estan las decisiones.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Problema:
    """Algo que esta mal en los datos.

    `bloqueante` separa dos cosas que no se deben confundir. Una referencia
    roto impide cargar: una oferta que apunta a un producto inexistente
    reventaria al armar un kit. Una imagen que falta no impide nada, solo se
    ve fea, y esconderla seria peor que cargarla.
    """

    bloqueante: bool
    clase: str
    detalle: str

    def __str__(self) -> str:
        marca = "BLOQUEA" if self.bloqueante else "carencia"
        return f"[{marca}] {self.clase}: {self.detalle}"


def normalizar_isbn(crudo: str | None) -> str | None:
    """Deja solo digitos y la X final. Devuelve None si no queda nada."""
    if not crudo:
        return None
    limpio = re.sub(r"[^0-9Xx]", "", crudo).upper()
    return limpio or None


def ean13(crudo: str | None) -> str | None:
    """El codigo de barras en EAN-13, la forma en que el catalogo lo guarda.

    Las tiendas devuelven a veces el UPC-A de 12 digitos (productos
    norteamericanos, como los Speedball). Es el mismo numero con un cero
    delante, y sin normalizarlo el mismo articulo podia quedar con dos llaves.
    Lo que no tiene 12 ni 13 digitos no es un codigo de barras: `None`.
    """
    digitos = re.sub(r"\D", "", crudo or "")
    if len(digitos) == 12:
        return "0" + digitos
    return digitos if len(digitos) == 13 else None


def isbn13_valido(crudo: str | None) -> bool:
    """Verifica los 13 digitos y el digito de control.

    No es formalismo. El error que de verdad ocurrio al construir la semilla
    fue raspar una pagina de CATEGORIA en vez de una ficha de producto: lo que
    volvio como ISBN era el codigo interno de la tienda (`732461`). Si eso
    entrara al catalogo, dos libros distintos podrian colisionar en la misma
    llave y el papa recibiria el que no pidio. El digito de control es lo que
    distingue un ISBN de un numero cualquiera del mismo largo.
    """
    isbn = normalizar_isbn(crudo)
    if not isbn or len(isbn) != 13 or not isbn.isdigit():
        return False
    if not isbn.startswith(("978", "979")):
        return False
    suma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn[:12]))
    control = (10 - suma % 10) % 10
    return control == int(isbn[12])


def pesos_a_centavos(crudo: Any) -> int:
    """Pasa un precio en pesos a centavos enteros.

    Acepta el formato de las tiendas colombianas (`132.000`, `$ 105.000`),
    donde el punto es separador de miles y NO un decimal. Tratarlo como
    decimal convertiria ciento treinta y dos mil pesos en ciento treinta y
    dos, y el kit saldria mil veces mas barato sin que nada se rompiera.
    """
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
    """Comprueba que cada capa apunte a algo que existe en la de abajo.

    Postgres tambien lo comprobaria con las llaves foraneas, pero el mensaje
    que da es el nombre de una restriccion y el identificador que fallo, sin
    decir en que fila de que CSV estaba. Hacerlo antes permite listar TODOS
    los problemas de una vez en vez de descubrirlos de uno en uno, que es la
    diferencia entre una correccion y veinte reintentos.
    """
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


# ---------------------------------------------------------------------------
# Lectura de los CSV curados
# ---------------------------------------------------------------------------

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
    """Los CSV guardan listas como `a|b|c` o como un JSON de cadena."""
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
    """Fecha de observacion, con la zona explicita.

    Se exige con zona porque la columna es `timestamptz`: una fecha ingenua
    la interpretaria Postgres en la zona de la sesion, y entonces la misma
    observacion tendria dos instantes distintos segun quien corriera la carga.
    """
    limpio = (crudo or "").strip()
    if not limpio:
        return datetime.now(UTC)
    try:
        valor = datetime.fromisoformat(limpio)
    except ValueError:
        return datetime.now(UTC)
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


# Claves que versiones viejas del CSV traian "por fidelidad" y que ningun filtro
# usa. `cantidades_declaradas` mezclaba empaque y medidas (ver el modelo); hoy
# eso vive en `unidades_por_empaque`. Cargarlas solo ensuciaria el producto.
_ATRIBUTOS_LEGADO = frozenset({"cantidades_declaradas", "frase_ancla"})


def atributos_de_csv(crudo: str | None) -> dict[str, Any]:
    """Los atributos de un producto tal como los exporto `volcar`."""
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


# ---------------------------------------------------------------------------
# Informe de calidad
# ---------------------------------------------------------------------------


@dataclass
class Informe:
    """Lo que se cargo y lo que le falta.

    Se imprime siempre, tambien cuando todo sale bien, porque el dato util no
    es "cargo" sino "cargo 242 productos, de los cuales 175 no tienen imagen".
    """

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


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

# Conceptos de libro que la semilla de Firecrawl surte.
#
# Se usan los codigos QUE YA EXISTEN (C034, C042, C048) en vez de inventar
# codigos nuevos, y eso corrige un error propio: la primera version creo
# `biblia-catolica` al lado de `C048 biblia` y `constitucion-politica` al lado
# de `C042 constitucion politica`. Dos conceptos para la misma cosa parten la
# demanda en dos (C048 decia 11 y el duplicado 8, cuando son 19) y le dan al
# clasificador dos destinos validos para el mismo renglon de la lista.
#
# `C034 diccionario` se partio una vez en dos (espanol e ingles) para no
# ofrecerle un diccionario de ingles a quien pidio uno de espanol. Ya no hace
# falta: C034 filtra por `idioma`, y el idioma se escribe igual sin importar el
# orden (`espanol-ingles`). Partido, el mismo diccionario ingles-espanol salia
# bien en un grado (curado en C034) y como hueco en otro (curado en el de
# ingles). La semilla todavia puede traer filas con `dic-ingles`: se leen como
# C034.
#
# Lo que cambia sobre el concepto existente es `tipo_item`: pasa de `util` a
# `libro_libre`, porque una biblia no es papeleria y el pipeline no debe
# buscarle sustitutos de papeleria.
CONCEPTOS_LIBRO = {
    "C034": ("Diccionario de espanol", ["diccionario", "diccionario de espanol", "dicc espanol"]),
    "C042": (
        "Constitucion Politica de Colombia",
        ["constitucion", "constitucion politica", "constitucion politica de colombia"],
    ),
    "C048": ("Biblia", ["biblia", "biblia catolica", "sagrada biblia"]),
}
# Codigos viejos de la semilla y el concepto en que viven ahora.
CONCEPTOS_LIBRO_FUSIONADOS = {"dic-ingles": "C034"}


def _uuid_estable(*partes: str) -> uuid.UUID:
    """Identificador derivado del contenido, para que la carga sea idempotente.

    Con UUID aleatorio, correr el cargador dos veces duplicaria todo. Con uno
    derivado de la llave natural, la segunda corrida actualiza las mismas
    filas. Es tambien lo que permite que la semilla de libros y los CSV de
    papeleria se refieran a los mismos conceptos sin coordinar identificadores
    a mano.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, "tukit:" + ":".join(partes))


# Quien "curo" las filas que vienen del raspado. No es una persona, y el
# catalogo tiene que poder distinguirlo de una fila que alguien reviso a mano.
AGENTE_FIRECRAWL = uuid.uuid5(uuid.NAMESPACE_URL, "tukit:agente:firecrawl")

# Columnas que el cargador SIEMBRA al insertar pero NO pisa al reescribir.
#
# Estas cuatro no las sabe el CSV: las averigua `enriquecer`, leyendo el
# empaque y el personaje del nombre y trayendo la portada de la ficha de la
# tienda. El upsert actualizaba toda columna presente en la fila, asi que
# volver a correr el cargador dejaba el catalogo como estaba antes: las
# imagenes en nulo y los empaques de vuelta en uno.
#
# El fallo era silencioso, que es lo peor de todo. El cargador informaba que
# habia escrito 330 productos, y era cierto; lo que no decia es que acababa de
# deshacer el enriquecimiento. La regla que lo evita es que el CSV manda sobre
# lo que el CSV sabe, y nada mas.
COLUMNAS_ENRIQUECIDAS = frozenset(
    {"imagen_url", "atributos", "unidades_por_empaque", "unidad_base", "personaje"}
)


class Cargador:
    def __init__(self, directorio: Path) -> None:
        self.dir = directorio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}

    # -- armado en memoria -------------------------------------------------

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
                # `tipo_item` ya viene en el CSV, y tenia que venir: marcarlo
                # solo en la base no duraba, porque la siguiente carga lo
                # devolvia a `util`. Asi le paso a C067, `muda de ropa`, que
                # es el unico concepto que un colegio pide y Tukit no debe
                # vender: el nino manda una muda que ya tiene.
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
        # Las librerias de la semilla de libros no estan en tiendas.csv: ese
        # fichero salio del raspado de papelerias. Se agregan aqui para que la
        # oferta de un libro tenga a quien pertenecer.
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
        # Desde 2026-10-11 el CSV trae el empaque (lo vuelca `volcar`). Si lo
        # trae, manda sobre la base; un CSV viejo sin la columna no lo pisa.
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
                    # `curado_por` es NOT NULL y a proposito: toda fila del
                    # catalogo tiene que poder decir quien la puso ahi. Es un
                    # identificador de usuario, no un texto libre.
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
                    # Un precio sin fecha de inicio no es un precio, es un
                    # numero: no se puede saber si sigue vigente ni comparar
                    # dos observaciones de la misma oferta en el tiempo.
                    "vigente_desde": _fecha(f.get("vigente_desde")),
                }
            )
        return ofertas, precios

    def _libros(
        self, conceptos: list[dict[str, Any]], tiendas: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Normaliza la semilla de libros a las tres capas.

        La semilla viene desnormalizada (una fila = un libro en una tienda a un
        precio) porque asi se observo y asi queda auditable. Aqui se parte: el
        libro es UN `producto_canonico` identificado por su ISBN, y cada tienda
        que lo vende es una `oferta_tienda` con su `precio_oferta`.

        Esa division es justo lo que el modelo plano anterior no podia
        expresar, y hay un caso en la semilla que lo demuestra: el ISBN
        9788428536523 se observo a 153.000 en una libreria y a 130.812 en otra.
        Con `precio` como columna del producto, uno de los dos numeros tenia
        que perderse.
        """
        filas = leer_csv(self.dir / "libros_firecrawl.csv")
        if not filas:
            return {"conceptos": [], "productos": [], "ofertas": [], "precios": []}

        por_slug = {t["slug"]: t["id"] for t in tiendas}
        # Los conceptos de papeleria ya tienen identificador propio en el CSV.
        # Engancharse a ESE, y no fabricar uno derivado del codigo, es lo que
        # evita el duplicado.
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
                # Lo unico que se le cambia a un concepto que ya existia. Su
                # demanda, sus sinonimos y su identificador se respetan: los
                # midio el corpus y los referencia el gold standard.
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
                    # La razon de ser de esta semilla. Con el default `util`,
                    # el pipeline le buscaria papeleria a una biblia.
                    "tipo_item": "libro_libre",
                    # El de ingles filtra por `monolingue`: el colegio que pide
                    # `ingles - ingles` no quiere el bilingue, y el que pide
                    # `diccionario de ingles` a secas acepta cualquiera.
                    "atributos_discriminantes": [],
                    "atributos_descriptivos": [],
                    # Un diccionario sirve para todas las materias del ano.
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

        # El nivel es propiedad del PRODUCTO, no de la oferta: una edicion no
        # es economica en una libreria y premium en otra. Como la semilla viene
        # desnormalizada, el mismo ISBN aparece en varias filas, y si cada una
        # declara un nivel distinto el que gana es el de la fila que se leyo
        # primero. Eso ya paso: una biblia quedo `confiable` por el precio de
        # una tienda cuando la otra la ponia en `premium`.
        #
        # Se comprueba en vez de elegir por silencio, porque la eleccion es de
        # curaduria y no del orden del fichero.
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
                    # `sku_interno` es obligatorio: es la referencia con la
                    # que Tukit nombra el producto, independiente de como lo
                    # llame cada tienda. Para un libro se deriva del ISBN,
                    # que ya es un identificador estable y unico.
                    "sku_interno": f"TK-LIB-{isbn}",
                    "nombre": f["titulo"],
                    "descripcion": None,
                    "marca": _texto(f.get("editorial")),
                    "nivel": f.get("nivel") or "confiable",
                    "personaje": None,
                    "imagen_url": _texto(f.get("imagen_url")),
                    # Lo que el titulo dice de los atributos que filtran (la
                    # edicion de una biblia, el idioma de un diccionario), lo
                    # que la semilla corrige a mano en `atributos`, y el ISBN.
                    # Con el ISBN solo, ninguna biblia declaraba `edicion` y
                    # `Biblia catolica` quedaba como hueco en los once grados.
                    "atributos": {
                        **extraer_atributos(f["titulo"], discriminantes.get(f["concepto_codigo"], ())),
                        **atributos_de_csv(f.get("atributos")),
                        "isbn13": isbn,
                    },
                    "ruta_categoria": "Libros",
                    "es_propio": False,
                    "es_representante_canonico": False,
                    "activo": True,
                    # Un libro es una unidad y no se vende por empaque. Aqui el
                    # 1 no es un default heredado: es el valor correcto.
                    "unidad_base": "unidad",
                    "unidades_por_empaque": 1,
                    # Alta para un libro con ISBN verificado: el vinculo no se
                    # adivino por parecido de texto, se leyo el identificador.
                    "quality_score": 0.9,
                    # Estas filas no las puso una persona sino un agente de
                    # raspado, y el catalogo tiene que poder decirlo: es la
                    # diferencia entre un precio que alguien confirmo y uno
                    # que se leyo de una pagina y puede haber cambiado.
                    "curado_por": AGENTE_FIRECRAWL,
                }
            elif not productos[isbn]["imagen_url"] and _texto(f.get("imagen_url")):
                # La misma edicion en dos tiendas: una puede tener portada y la
                # otra no. Se queda la que exista.
                productos[isbn]["imagen_url"] = _texto(f["imagen_url"])

            oferta_id = _uuid_estable("oferta", isbn, slug)
            ofertas.append(
                {
                    "id": oferta_id,
                    "producto_canonico_id": productos[isbn]["id"],
                    "tienda_id": por_slug[slug],
                    "referencia_externa": _texto(f.get("sku_tienda")) or isbn,
                    "url": _texto(f.get("url_origen")),
                    # `ean` y no un valor nuevo para ISBN, porque un ISBN-13
                    # ES un EAN-13: los prefijos 978 y 979 son el rango que
                    # GS1 reservo para libros. Agregar `isbn` al vocabulario
                    # habria sido inventar una distincion que no existe.
                    #
                    # Lo que importa del valor es que estos vinculos NO se
                    # adivinaron por parecido de texto: se leyo el
                    # identificador en la ficha. De ahi la confianza en 1.0,
                    # frente al canal mayorista donde vincular por EAN no es
                    # ni posible y toca ir por atributos.
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
                    # `scraper` y no un valor propio para Firecrawl: la
                    # columna clasifica COMO se obtuvo el precio (raspado,
                    # capturado a mano, o de referencia), no con que
                    # herramienta. Que fue Firecrawl ya lo dice
                    # `producto_canonico.curado_por`, y de que tienda salio lo
                    # dice `oferta_tienda.tienda_id`: no se pierde nada.
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
        """Cuenta lo que falta para que un kit se pueda mostrar.

        El orden de la lista es el orden en que duelen. Sin imagen el papa no
        reconoce el producto; sin atributos el resolutor no puede filtrar por
        las restricciones que el colegio escribio; sin empaque declarado la
        cuenta de cuantos comprar es un uno asumido.
        """
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
            # Los tres kits necesitan tres niveles. Un concepto que solo tiene
            # nivel `confiable` no puede aparecer en el kit Ahorrador ni en el
            # Premium con una opcion distinta.
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

    # -- escritura --------------------------------------------------------

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy import func, literal_column
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("catalogo")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                # El orden es el de las dependencias: no se puede insertar una
                # oferta antes que su producto.
                for tabla in ("tienda", "concepto", "producto_canonico", "oferta_tienda", "precio_oferta"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    if tabla == "producto_canonico":
                        await _liberar_skus(conexion, objeto, filas)
                    sentencia = insert(objeto).values(filas)
                    # `ON CONFLICT DO UPDATE` sobre la llave primaria es lo que
                    # hace la carga repetible: los identificadores se derivan
                    # del contenido, asi que la segunda corrida actualiza las
                    # mismas filas en vez de duplicarlas.
                    actualizables = {
                        c.name: sentencia.excluded[c.name]
                        for c in objeto.columns
                        if c.name not in [k.name for k in objeto.primary_key.columns]
                        and c.name in filas[0]
                        and not (tabla == "producto_canonico" and c.name in COLUMNAS_ENRIQUECIDAS)
                        # `admite_personaje` se deduce de los productos que de
                        # hecho tienen personaje, no se declara. El CSV decia
                        # que 7 conceptos lo admitian cuando el catalogo ya
                        # tenia reglas de Barbie y balones de Avengers en 17.
                        and not (tabla == "concepto" and c.name == "admite_personaje")
                    }
                    if tabla == "producto_canonico":
                        # `atributos` se combinaba (base || CSV) para que una
                        # correccion a mano llegara a otra base sin borrar lo que
                        # `enriquecer` ya sabia. Desde que `volcar` exporta lo que
                        # la base sabe, el CSV trae el producto completo: si
                        # declara atributos, son TODOS, y los reemplaza.
                        # Combinados, una clave que la curaduria quito del CSV (la
                        # `forma` del pincel de agua) seguia viva en cada base que
                        # ya la tenia. Vacio, no dice nada y la base conserva lo suyo.
                        vacio = literal_column("'{}'::jsonb")
                        actualizables["atributos"] = func.coalesce(
                            func.nullif(sentencia.excluded.atributos, vacio), objeto.c.atributos
                        )
                        # Lo mismo con lo que el CSV sabe ahora y antes no: el
                        # personaje y la portada mandan si vienen; el empaque, si
                        # el CSV tiene la columna. Sin esto, recargar sobre una base
                        # existente dejaba el kit de 40 jumpers en empaque 1.
                        actualizables["imagen_url"] = func.coalesce(
                            sentencia.excluded.imagen_url, objeto.c.imagen_url
                        )
                        # El personaje no se combina: vacio en el CSV es una
                        # decision («Kiut» es la marca, no un personaje), y con
                        # coalesce la base conservaba el viejo y el producto
                        # seguia fuera de los kits canonicos. Desde que `volcar`
                        # exporta la base, el CSV trae el personaje de todos.
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
    """Aparta el sku de los productos que lo cambian antes del upsert.

    `nivelar` permuta etiquetas, y con ellas los sku semilla: el economico pasa a
    `TK-C011-PRE` y el premium a `TK-C011-ECO`. El upsert por id escribe fila por
    fila y el indice unico de `sku_interno` se revisa en cada una, asi que la
    primera fila choca con la que todavia tiene ese sku. Se les pone uno
    provisional derivado del id (unico por construccion) y el upsert les da el
    definitivo en la misma transaccion.
    """
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
    """Mide las carencias contra la base viva, no contra los CSV.

    La distincion importa y costo un informe enganoso. `enriquecer` averigua
    el empaque, la portada y el personaje y los escribe en la base; los CSV no
    los tienen ni los van a tener. Midiendo el CSV, el cargador seguia
    diciendo que 260 de 260 productos tenian el empaque asumido en 1 mucho
    despues de haberlo corregido para cien de ellos.

    Tambien cambia aqui la definicion de ese numero. Contar cada producto con
    `unidades_por_empaque = 1` como carencia era un error de partida: un
    cuaderno suelto y una regla SON una unidad, y decir que les falta el
    empaque es contar como defecto que el dato correcto sea uno. Lo que si es
    carencia es un nombre que anuncia un empaque y quedo en uno, y eso es lo
    que se mide.
    """
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
        # Las carencias se vuelven a medir contra la base, que es la unica que
        # sabe lo que `enriquecer` averiguo despues de los CSV.
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
