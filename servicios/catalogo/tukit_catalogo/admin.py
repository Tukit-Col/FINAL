"""Front de administracion del catalogo: el gemelo interactivo de `vista`.

`vista` saca un HTML para MIRAR el catalogo; esto lo saca para TRABAJARLO. Es
la pantalla donde una persona deja el catalogo listo antes de que un papa vea
nada: ve cada concepto con sus productos, sus fotos y sus etiquetas, y sobre
eso agrega libros, agrega utiles (apoyandose en las tiendas), corrige el
empaque, y descarta lo que no vendemos. Cuando termina, vuelca a los CSV para
que el corpus versionado reproduzca ese estado.

Por que un servidor y no otro HTML estatico: `vista` no puede escribir, y el
trabajo aqui es escribir. Por que la biblioteca estandar y no un framework: el
resto del catalogo no tiene dependencias de web a proposito (`vista` es un
archivo que se abre y ya), y una pantalla de curaduria que corre una persona en
su maquina no justifica arrastrar FastAPI, un build de front y un servidor de
aplicaciones al monorepo. `http.server` alcanza de sobra.

Que reusa, sin reimplementar nada del dominio:

  - La lectura sale de la misma consulta que `vista`, extendida con los ids que
    hacen falta para editar (producto, concepto).
  - El alta de un util se apoya en `tiendas.buscar` con el mismo quinto filtro
    (`_coincide`) que el resto del catalogo, y el alta se materializa encolando
    una propuesta (`_encolar`) y aprobandola (`resolver`), el MISMO camino por
    el que entra lo que se revisa de una lista. Aqui no hay puerta
    (`abrir_revision`) porque esto es CURADURIA proactiva, igual que
    `completar`: se llena el catalogo ANTES de que exista un papa que pregunte,
    no durante. La puerta protege el flujo del acudiente, no este.
  - El volcado a CSV es `volcar`, tal cual.

Por que vive en `catalogo` y no en `apps/admin/` (coherencia con el lock):

  ARQUITECTURA.md (ADR 0008 y ADR 0012) fija que la UI de personal interno es
  la app `admin`, y que al disolverse MS-BFFAdmin la administracion se resuelve
  con "consultas locales de `catalogo`". Esto es precisamente eso: curaduria
  LOCAL del dominio de catalogo, gemelo de `vista` (que tambien renderiza HTML
  desde el servicio y nadie lo considera fuera de lugar). No cruza ninguna
  frontera --solo importa `.` y `tukit_comun`, verificado por las pruebas de
  fronteras-- asi que el dominio queda donde manda el lock. El dia que la
  administracion crezca a varias pantallas multi-rol (proveedor, editorial,
  operador), la composicion "baja al cliente" en `apps/admin/`; esas pantallas
  llamaran a estas MISMAS funciones de dominio (`_leer`, `agregar_util`,
  `agregar_libro`, `volcar`), que se quedan aqui. Esto es el precursor de esa
  app, no un servicio de UI paralelo.

Uso:

    python -m tukit_catalogo.admin            # sirve en localhost:8000
    python -m tukit_catalogo.admin --abrir     # y abre el navegador
    python -m tukit_catalogo.admin --puerto 9000
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from . import tiendas
from .descubrir import _encolar, resolver
from .dominio.propuesta import (  # re-exportados: la vista http.server y su test los usan por nombre
    _ean_valido,  # noqa: F401
    construir_propuesta_libro,
    construir_propuesta_util,
)
from .modelos import Nivel, TipoItem

# ponytail: `volcar` es CLI batch de un solo llamador HTTP (el boton "volcar" de
# la consola); se invoca entero, no tiene SQL que un request reuse pieza a pieza
# -> a repositorios solo si un endpoint necesitara sus consultas por separado.
from .volcar import _principal as volcar_principal

# Las tres tiendas que el catalogo ya usa, en el orden en que `completar` y
# `crear_util` las consultan. El alta asistida busca en las tres a la vez.
SLUGS_TIENDA = ("exito", "panamericana", "grancentral")


# ---------------------------------------------------------------------------
# Lectura: el mismo modelo que `vista`, con los ids que la edicion necesita.
# ---------------------------------------------------------------------------


async def _leer() -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Trae los conceptos con sus productos, para pintar y para editar.

    Es la consulta de `vista._leer` con dos anadidos que la edicion necesita y
    la vista no: el id del concepto (para colgarle un alta) y el id del producto
    con su empaque (para corregirlo). El precio sigue siendo el mas barato entre
    tiendas, por la misma razon que en `vista`: es la cifra honesta.
    """
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    text("""
                SELECT c.id AS cid, c.codigo, c.nombre_canonico, c.tipo_item,
                       c.frecuencia_demanda, c.sinonimos,
                       c.atributos_discriminantes, c.atributos_descriptivos,
                       p.id AS pid, p.nombre, p.nivel, p.imagen_url, p.personaje, p.marca,
                       p.atributos, p.unidad_base, p.unidades_por_empaque, p.quality_score,
                       t.nombre AS tienda, o.url,
                       (SELECT min(pr.valor_centavos)
                          FROM oferta_tienda o2
                          JOIN precio_oferta pr ON pr.oferta_id = o2.id
                         WHERE o2.producto_canonico_id = p.id) AS precio
                  FROM concepto c
                  LEFT JOIN producto_canonico p ON p.concepto_id = c.id AND p.activo
                  LEFT JOIN LATERAL (
                        SELECT * FROM oferta_tienda o1
                         WHERE o1.producto_canonico_id = p.id AND o1.activo LIMIT 1
                  ) o ON true
                  LEFT JOIN tienda t ON t.id = o.tienda_id
                 WHERE c.activo
                 ORDER BY c.frecuencia_demanda DESC, c.codigo,
                          CASE p.nivel WHEN 'economico' THEN 1 WHEN 'confiable' THEN 2 ELSE 3 END
            """)
                )
            ).all()
            tiendas_activas = (
                await conexion.execute(text("SELECT count(*) FROM tienda WHERE activa"))
            ).scalar_one()
            en_cola = (
                await conexion.execute(
                    text("SELECT count(*) FROM propuesta_producto WHERE estado='pendiente'")
                )
            ).scalar_one()
    finally:
        await motor.cerrar()

    conceptos: list[dict[str, Any]] = []
    indice: dict[str, dict[str, Any]] = {}
    for f in filas:
        bloque = indice.get(f.codigo)
        if bloque is None:
            bloque = {
                "id": str(f.cid),
                "codigo": f.codigo,
                "nombre": f.nombre_canonico,
                "tipo_item": f.tipo_item,
                "demanda": f.frecuencia_demanda,
                "sinonimos": list(f.sinonimos or ()),
                # Las claves que el concepto declara: son las casillas que el
                # diálogo de editar pinta para llenar los `atributos` de cada
                # producto (color, tamaño, hojas...). Discriminantes primero
                # porque son las que de verdad separan un producto de otro.
                "atributos_clave": list(f.atributos_discriminantes or ())
                + list(f.atributos_descriptivos or ()),
                "productos": [],
            }
            indice[f.codigo] = bloque
            conceptos.append(bloque)
        if f.pid is not None:
            bloque["productos"].append(
                {
                    "id": str(f.pid),
                    "nombre": f.nombre,
                    "nivel": f.nivel,
                    "imagen_url": f.imagen_url,
                    "personaje": f.personaje,
                    "marca": f.marca,
                    "atributos": f.atributos,
                    "unidad_base": f.unidad_base,
                    "unidades_por_empaque": f.unidades_por_empaque,
                    "quality_score": f.quality_score,
                    "tienda": f.tienda,
                    "url": f.url,
                    "precio": f.precio,
                }
            )

    comprables = [c for c in conceptos if c["tipo_item"] == TipoItem.UTIL.value]
    productos = [p for c in conceptos for p in c["productos"]]
    resumen = {
        "productos": len(productos),
        "conceptos": len(conceptos),
        "comprables": len(comprables),
        "completos": sum(1 for c in comprables if len({p["nivel"] for p in c["productos"]}) >= 3),
        "sin_producto": sum(1 for c in comprables if not c["productos"]),
        "con_foto": sum(1 for p in productos if p["imagen_url"]),
        "tiendas": tiendas_activas,
        "por_revisar": sum(1 for p in productos if float(p["quality_score"] or 0) < 0.5),
        "por_revisar_cola": en_cola,
    }
    return conceptos, resumen


async def _leer_cola() -> list[dict[str, Any]]:
    """Las propuestas pendientes, agrupadas por concepto para revisarlas.

    Es la cola que llena `completar` (curaduria adelantada) y `descubrir`
    (revision de una lista): candidatos que una persona todavia no ha mirado.
    Se agrupan por concepto porque asi se decide --"para *lentejuelas* tengo
    estos tres, cual va en cada nivel"--, y cada fila trae lo que la tarjeta
    necesita para elegir sin salir a la tienda: nombre, precio, foto, marca,
    tienda, nivel sugerido y el enlace por si hay que verificar la ficha.
    """
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    text("""
                SELECT pp.id AS ppid, pp.texto_origen, pp.nombre, pp.precio_centavos,
                       pp.nivel_sugerido, pp.marca, pp.imagen_url, pp.url, pp.puntaje,
                       pp.ean, pp.origen, pp.concepto_sugerido,
                       c.id AS cid, c.codigo, c.nombre_canonico, c.frecuencia_demanda,
                       t.nombre AS tienda
                  FROM propuesta_producto pp
                  LEFT JOIN concepto c ON c.id = pp.concepto_id
                  LEFT JOIN tienda t ON t.id = pp.tienda_id
                 WHERE pp.estado = 'pendiente'
                 ORDER BY c.frecuencia_demanda DESC NULLS LAST, c.codigo,
                          CASE pp.nivel_sugerido WHEN 'economico' THEN 1
                               WHEN 'confiable' THEN 2 ELSE 3 END,
                          pp.precio_centavos
            """)
                )
            ).all()
    finally:
        await motor.cerrar()

    grupos: dict[str, dict[str, Any]] = {}
    orden: list[str] = []
    for f in filas:
        clave = f.codigo or f"nuevo:{f.concepto_sugerido}"
        grupo = grupos.get(clave)
        if grupo is None:
            grupo = {
                "codigo": f.codigo,
                "concepto_id": str(f.cid) if f.cid else None,
                "nombre": f.nombre_canonico or f"nuevo: {f.concepto_sugerido}",
                "demanda": f.frecuencia_demanda or 0,
                "es_nuevo": f.cid is None,
                "propuestas": [],
            }
            grupos[clave] = grupo
            orden.append(clave)
        grupo["propuestas"].append(
            {
                "id": str(f.ppid),
                "id_corto": str(f.ppid)[:8],
                "texto_origen": f.texto_origen,
                "nombre": f.nombre,
                "ean": f.ean,
                "precio": f.precio_centavos,
                "nivel_sugerido": f.nivel_sugerido,
                "marca": f.marca,
                "imagen_url": f.imagen_url,
                "url": f.url,
                "puntaje": float(f.puntaje or 0),
                "origen": f.origen,
                "tienda": f.tienda,
            }
        )
    return [grupos[k] for k in orden]


# ---------------------------------------------------------------------------
# Escritura: se apoya en los mismos seams que el resto del catalogo.
# ---------------------------------------------------------------------------


async def _fijar_columna_producto(producto_id: str, **columnas: Any) -> int:
    """UPDATE de una o varias columnas de un producto por id. Devuelve filas."""
    from sqlalchemy import update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            resultado = await conexion.execute(
                update(producto).where(producto.c.id == uuid.UUID(producto_id)).values(**columnas)
            )
            return resultado.rowcount or 0
    finally:
        await motor.cerrar()


async def _editar_producto(
    producto_id: str,
    *,
    nombre: str | None,
    nivel: str | None,
    imagen_url: str | None,
    precio_centavos: int | None,
    marca: str | None = None,
    concepto_id: str | None = None,
    atributos: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Edita un producto suelto en una transacción.

    Nombre, nivel, foto, marca, concepto y atributos viven en
    `producto_canonico`; el precio vive en `precio_oferta`, colgado de las
    ofertas del producto. Curar a mano un duplicado es corregir esas cosas
    juntas: si el precio se escribe pero la fila del producto falla, no queremos
    un precio huérfano.

    Reasignar el concepto es solo cambiar la llave foránea `concepto_id`: no
    toca `sku_interno` (sigue único) ni borra las ofertas. Es lo que arregla
    "veo resmas en el concepto hojas": se mueve el producto a su concepto real.
    Los `atributos` (color, tamaño, hojas...) llegan como un diccionario ya
    armado desde las casillas que el concepto declara; se sobrescribe entero.
    """
    from sqlalchemy import text, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    columnas: dict[str, Any] = {}
    if nombre:
        columnas["nombre"] = nombre
    if nivel:
        columnas["nivel"] = nivel
    if imagen_url is not None:  # cadena vacía = borrar la foto a propósito
        columnas["imagen_url"] = imagen_url or None
    if marca is not None:  # cadena vacía = borrar la marca a propósito
        columnas["marca"] = marca or None
    if concepto_id:
        columnas["concepto_id"] = uuid.UUID(concepto_id)
    if atributos is not None:  # {} = vaciar los atributos a propósito
        columnas["atributos"] = atributos

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            existe = (
                await conexion.execute(
                    text("SELECT 1 FROM producto_canonico WHERE id = :pid AND activo"),
                    {"pid": producto_id},
                )
            ).first()
            if not existe:
                return False, "No encontré ese producto."
            if concepto_id:
                concepto_ok = (
                    await conexion.execute(
                        text("SELECT 1 FROM concepto WHERE id = :cid AND activo"),
                        {"cid": concepto_id},
                    )
                ).first()
                if not concepto_ok:
                    return False, "Ese concepto no existe o no está activo."
            if columnas:
                await conexion.execute(
                    update(producto).where(producto.c.id == uuid.UUID(producto_id)).values(**columnas)
                )
            if precio_centavos is not None:
                await conexion.execute(
                    text("""
                        UPDATE precio_oferta SET valor_centavos = :v
                         WHERE oferta_id IN (
                            SELECT id FROM oferta_tienda
                             WHERE producto_canonico_id = :pid AND activo
                         )
                    """),
                    {"v": precio_centavos, "pid": producto_id},
                )
    finally:
        await motor.cerrar()
    return True, "Producto actualizado."


async def _borrar_producto(producto_id: str) -> tuple[bool, str]:
    """Borra un producto del catálogo EN DURO, con sus ofertas y precios.

    Un duplicado o una basura (el morral universitario en un concepto de niños)
    se quita del todo, no se desactiva. La razón es el corpus: `volcar` exporta
    TODA `producto_canonico` a CSV sin mirar la columna de actividad -incluso la
    escribe-, así que un producto desactivado seguiría ensuciando el CSV curado
    que es la fuente de verdad reproducible. Para que el CSV quede limpio, el
    producto tiene que desaparecer de la base. Se borra en una sola transacción
    de las cuatro tablas -precio, oferta, propuesta, producto- para no dejar
    huérfanos.

    La propuesta se borra ANTES que el producto a propósito. Un producto que
    nació de aprobar una propuesta deja esa fila en `propuesta_producto`
    apuntándolo; la llave foránea la pondría en NULL al borrar el producto, pero
    un CHECK (`propuesta_aprobada_tiene_producto`) prohíbe una propuesta
    aprobada sin producto, así que ese SET NULL falla. La propuesta ya cumplió
    su papel -materializó el producto-, y si el producto se va, su rastro en la
    cola también.
    """
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            existe = (
                await conexion.execute(
                    text("SELECT 1 FROM producto_canonico WHERE id = :pid"),
                    {"pid": producto_id},
                )
            ).first()
            if not existe:
                return False, "No encontré ese producto."
            # Los precios cuelgan de las ofertas y las ofertas del producto: se
            # borra de abajo hacia arriba para respetar las llaves foráneas.
            await conexion.execute(
                text("""
                    DELETE FROM precio_oferta
                     WHERE oferta_id IN (
                        SELECT id FROM oferta_tienda WHERE producto_canonico_id = :pid
                     )
                """),
                {"pid": producto_id},
            )
            await conexion.execute(
                text("DELETE FROM oferta_tienda WHERE producto_canonico_id = :pid"),
                {"pid": producto_id},
            )
            await conexion.execute(
                text("DELETE FROM propuesta_producto WHERE producto_canonico_id = :pid"),
                {"pid": producto_id},
            )
            await conexion.execute(
                text("DELETE FROM producto_canonico WHERE id = :pid"),
                {"pid": producto_id},
            )
    finally:
        await motor.cerrar()
    return True, "Producto borrado del catálogo."


async def _fijar_tipo_concepto(concepto_id: str, tipo_item: str) -> int:
    """Marca el tipo de un concepto (por ejemplo `no_comprar`). Devuelve filas."""
    from sqlalchemy import update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            resultado = await conexion.execute(
                update(concepto).where(concepto.c.id == uuid.UUID(concepto_id)).values(tipo_item=tipo_item)
            )
            return resultado.rowcount or 0
    finally:
        await motor.cerrar()


async def _no_surtir_concepto(concepto_id: str) -> tuple[bool, str]:
    """Cierra un concepto: lo marca 'no_comprar' y descarta sus pendientes.

    Las dos cosas van juntas y en una transacción: si el concepto no se surte
    (uniformes, cosas que el colegio vende), sus candidatos en cola dejan de
    tener sentido y no deben reaparecer la próxima vez que se abra la cola. Es
    la versión de conjunto del `no_surtir` de `resolver`, que actúa sobre UNA
    propuesta; aquí el gesto es sobre el concepto entero.
    """
    from sqlalchemy import update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    propuesta = Base.metadata.tables["propuesta_producto"]
    motor = crear_motor("catalogo")
    try:
        cid = uuid.UUID(concepto_id)
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    update(concepto).where(concepto.c.id == cid).values(tipo_item="no_comprar")
                )
            ).rowcount or 0
            if not filas:
                return False, "No encontré ese concepto."
            descartadas = (
                await conexion.execute(
                    update(propuesta)
                    .where(propuesta.c.concepto_id == cid, propuesta.c.estado == "pendiente")
                    .values(estado="rechazada", motivo="concepto no_comprar", resuelta_en=datetime.now(UTC))
                )
            ).rowcount or 0
    finally:
        await motor.cerrar()
    return True, f"Concepto marcado no_comprar; {descartadas} candidatos descartados."


async def _concepto_por_id(concepto_id: str) -> tuple[uuid.UUID, str] | None:
    """(id, nombre_canonico) de un concepto, o None si no existe."""
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(concepto.c.id, concepto.c.nombre_canonico).where(
                        concepto.c.id == uuid.UUID(concepto_id)
                    )
                )
            ).first()
    finally:
        await motor.cerrar()
    return (fila.id, fila.nombre_canonico) if fila else None


async def _tienda_por_slug(slug: str) -> uuid.UUID | None:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    tienda = Base.metadata.tables["tienda"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            return (
                await conexion.execute(select(tienda.c.id).where(tienda.c.slug == slug))
            ).scalar_one_or_none()
    finally:
        await motor.cerrar()


def buscar_candidatos(consulta: str) -> list[tuple[str, tiendas.Oferta]]:
    """Las tres tiendas con el quinto filtro puesto, de mas barato a mas caro.

    Es el mismo cuerpo que `crear_util` usa para armar su lista de candidatos,
    sin la puerta: la curaduria proactiva no exige una lista sin revisar. Cada
    candidato lleva su slug para poder encolarlo despues contra la tienda
    correcta.
    """
    candidatos: list[tuple[str, tiendas.Oferta]] = []
    for slug in SLUGS_TIENDA:
        for oferta in tiendas.buscar(slug, consulta):
            if not tiendas._coincide(oferta.nombre, consulta):
                continue
            if oferta.precio_cop <= 0 or not oferta.disponible:
                continue
            candidatos.append((slug, oferta))
    candidatos.sort(key=lambda par: par[1].precio_cop)
    return candidatos


async def agregar_util(concepto_id: str, slug: str, oferta: tiendas.Oferta, nivel: str) -> tuple[bool, str]:
    """Encola el candidato elegido y lo aprueba: queda como producto del catalogo.

    Dos pasos deliberados y reusados tal cual del flujo de revision: primero
    `_encolar` mete la propuesta (con `version_lista_id=None`, porque esto es
    curaduria, no la revision de una lista concreta), y despues `resolver` la
    aprueba, que es donde `resolver` le saca empaque y atributos del nombre y
    nace el producto con su oferta y su precio. No se reimplementa ese insert:
    se llama al mismo que aprueba lo que llega de una lista, para que el alta a
    mano y la aprobada en revision sean el mismo producto con el mismo puntaje.
    """
    tienda_id = await _tienda_por_slug(slug)
    if tienda_id is None:
        return False, f"No conozco la tienda '{slug}'."

    resuelto = await _concepto_por_id(concepto_id)
    if resuelto is None:
        return False, "Ese concepto ya no existe."
    _, nombre_concepto = resuelto

    propuesta = construir_propuesta_util(
        uuid.UUID(concepto_id), nombre_concepto, slug, tienda_id, oferta, nivel
    )
    pid = propuesta["id"]
    encoladas = await _encolar([propuesta])
    if not encoladas:
        # La llave natural (tienda, referencia) ya estaba: puede que sea un
        # producto que ya tenemos, o una propuesta pendiente. Se intenta
        # aprobar de todos modos, que es idempotente.
        pass
    codigo = await resolver(str(pid)[:8], aprobar=True, nivel=nivel, motivo=None)
    if codigo != 0:
        return False, "El candidato se encolo pero no se pudo aprobar. Revisa la cola con --pendientes."
    return True, f"Agregado a {nombre_concepto}: {oferta.nombre[:60]} ({nivel})."


async def aprobar_propuesta(id_corto: str, nivel: str) -> tuple[bool, str]:
    """Aprueba una propuesta de la cola: nace el producto, su oferta y su precio.

    No reimplementa el alta: llama a `resolver` --aprobar, el MISMO camino por
    el que se aprueba lo que llega de una lista de colegio. La persona puede
    corregir el nivel sugerido antes de aprobar (el candidato barato que la
    consulta puso en 'confiable' quiza es en realidad el 'economico').
    """
    codigo = await resolver(id_corto, aprobar=True, nivel=nivel, motivo=None)
    if codigo != 0:
        return False, "No se pudo aprobar. Puede que ya esté resuelta o le falte concepto."
    return True, f"Aprobada como {nivel}."


async def rechazar_propuesta(id_corto: str, motivo: str | None, no_surtir: bool) -> tuple[bool, str]:
    """Rechaza una propuesta. Con `no_surtir`, marca el concepto 'no_comprar'.

    Mismo `resolver` con `aprobar=False`. El rechazo corriente descarta ESTE
    candidato y deja el concepto abierto; `no_surtir` cierra el concepto entero
    (uniformes, cosas que no vendemos), que es la señal que el flujo del papá
    lee para mandarlo aparte en vez de sumarlo al kit.
    """
    codigo = await resolver(id_corto, aprobar=False, nivel=None, motivo=motivo, no_surtir=no_surtir)
    if codigo != 0:
        return False, "No se pudo rechazar. Puede que ya esté resuelta."
    return True, ("Concepto marcado no_comprar." if no_surtir else "Candidato descartado.")


async def agregar_libro(
    concepto_id: str, isbn: str, titulo: str, precio_cop: int, slug: str, nivel: str
) -> tuple[bool, str]:
    """Alta de un libro por ISBN, aprobada en el acto. Mismo camino que el util.

    Un libro no se busca (lo identifica el ISBN de una edicion, no un titulo),
    asi que aqui no hay tienda que consultar: la persona escribe ISBN, titulo y
    precio. Igual pasa por encolar + aprobar para que sea el mismo producto que
    nace de una revision.
    """
    from .cargador import isbn13_valido, normalizar_isbn

    isbn = normalizar_isbn(isbn) or ""
    if not isbn13_valido(isbn):
        return False, f"El ISBN '{isbn}' no pasa el digito de control."

    tienda_id = await _tienda_por_slug(slug)
    if tienda_id is None:
        return False, f"No conozco la tienda '{slug}'."
    resuelto = await _concepto_por_id(concepto_id)
    if resuelto is None:
        return False, "Ese concepto ya no existe."
    _, nombre_concepto = resuelto

    propuesta = construir_propuesta_libro(
        uuid.UUID(concepto_id), nombre_concepto, slug, tienda_id, isbn, titulo, precio_cop, nivel
    )
    pid = propuesta["id"]
    await _encolar([propuesta])
    codigo = await resolver(str(pid)[:8], aprobar=True, nivel=nivel, motivo=None)
    if codigo != 0:
        return False, "El libro se encolo pero no se pudo aprobar."
    return True, f"Libro agregado a {nombre_concepto}: {titulo[:60]}."


# ---------------------------------------------------------------------------
# La pagina: HTML + un poco de JS para las acciones (fetch a los POST).
# ---------------------------------------------------------------------------

ESTILOS = """
:root { --tinta:#16181d; --suave:#6b7280; --linea:#e5e7eb; --fondo:#fbfbfc;
  --ok:#15803d; --aviso:#b45309; --malo:#b91c1c; --acento:#1d4ed8; }
* { box-sizing:border-box; }
body { margin:0; background:var(--fondo); color:var(--tinta);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }
header { background:#fff; border-bottom:1px solid var(--linea); padding:24px 32px; }
h1 { margin:0 0 4px; font-size:22px; letter-spacing:-.02em; }
.sub { color:var(--suave); font-size:13px; }
.cifras { display:flex; flex-wrap:wrap; gap:26px; margin-top:16px; }
.cifra b { display:block; font-size:22px; font-variant-numeric:tabular-nums; }
.cifra span { color:var(--suave); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
main { padding:22px 32px 80px; }
.barra { position:sticky; top:0; z-index:5; background:var(--fondo); padding:12px 0;
  border-bottom:1px solid var(--linea); margin-bottom:20px; display:flex; gap:12px; align-items:center; }
.barra input, .barra select, button { font:inherit; padding:7px 11px; border:1px solid var(--linea);
  border-radius:7px; background:#fff; }
.barra input { width:280px; }
button { cursor:pointer; }
button.primario { background:var(--acento); color:#fff; border-color:var(--acento); }
button.peligro { color:var(--malo); border-color:#fecaca; }
button.mini { font-size:12px; padding:4px 9px; }
.concepto { margin-bottom:26px; background:#fff; border:1px solid var(--linea);
  border-radius:11px; overflow:hidden; }
.concepto.destacado { border-color:#fde68a; box-shadow:0 0 0 3px #fffbeb; }
.cab { display:flex; align-items:center; gap:11px; padding:12px 16px;
  border-bottom:1px solid var(--linea); flex-wrap:wrap; }
.cab h2 { margin:0; font-size:15px; }
.cab .cod { color:var(--suave); font-size:12px; font-variant-numeric:tabular-nums; }
.cab .acciones { margin-left:auto; display:flex; gap:7px; }
.pill { font-size:11px; padding:2px 8px; border-radius:999px; border:1px solid var(--linea);
  color:var(--suave); }
.pill.completo { color:var(--ok); border-color:#bbf7d0; background:#f0fdf4; }
.pill.parcial { color:var(--aviso); border-color:#fde68a; background:#fffbeb; }
.pill.vacio { color:var(--malo); border-color:#fecaca; background:#fef2f2; }
.pill.libro { color:var(--acento); border-color:#bfdbfe; background:#eff6ff; }
.rejilla { display:grid; gap:1px; background:var(--linea);
  grid-template-columns:repeat(auto-fill,minmax(228px,1fr)); }
.prod { background:#fff; padding:13px; display:flex; flex-direction:column; gap:6px; }
.prod img { width:100%; height:128px; object-fit:contain; background:#fff; }
.sinfoto { width:100%; height:128px; display:grid; place-items:center; background:#f6f7f9;
  color:#b6bcc6; font-size:12px; border-radius:6px; }
.nom { font-size:13px; line-height:1.35; min-height:34px; }
.precio { font-size:17px; font-variant-numeric:tabular-nums; font-weight:600; }
.meta { font-size:11px; color:var(--suave); display:flex; gap:7px; flex-wrap:wrap; align-items:center; }
.nivel { font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; font-weight:600; }
.nivel.economico { color:var(--ok); } .nivel.confiable { color:var(--acento); }
.nivel.premium { color:#7c3aed; }
.attrs { font-size:11px; color:var(--suave); }
.attrs code { background:#f2f3f5; padding:1px 5px; border-radius:4px; margin-right:3px; }
.meta .marca { color:#475569; }
.attrs-edit { display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; margin-bottom:6px; }
.attr-fila { display:flex; flex-direction:column; gap:2px; }
.attr-fila label { font-size:11px; color:var(--suave); text-transform:capitalize; }
.attr-fila input { padding:5px 7px; }
.empaque { display:flex; gap:5px; align-items:center; font-size:11px; }
.empaque input { width:52px; font:inherit; padding:2px 5px; border:1px solid var(--linea);
  border-radius:5px; }
.prod-acc { display:flex; gap:6px; margin-top:auto; padding-top:6px; }
.prod-acc .mini { flex:1; }
.oculto { display:none !important; }
dialog { border:none; border-radius:12px; padding:0; width:min(560px,92vw);
  box-shadow:0 12px 48px rgba(0,0,0,.22); }
dialog .cuerpo { padding:22px 24px; }
dialog h3 { margin:0 0 4px; } dialog .pista { color:var(--suave); font-size:13px; margin-bottom:16px; }
dialog label { display:block; font-size:12px; color:var(--suave); margin:10px 0 3px; }
dialog input, dialog select { width:100%; font:inherit; padding:8px 10px;
  border:1px solid var(--linea); border-radius:7px; }
dialog .fila { display:flex; gap:12px; } dialog .fila > * { flex:1; }
dialog .pie { display:flex; justify-content:flex-end; gap:9px; margin-top:20px; }
.candidatos { margin-top:14px; display:flex; flex-direction:column; gap:8px;
  max-height:320px; overflow:auto; }
.cand { display:flex; gap:11px; align-items:center; border:1px solid var(--linea);
  border-radius:8px; padding:8px; }
.cand img { width:46px; height:46px; object-fit:contain; }
.cand .info { flex:1; font-size:12.5px; } .cand .p { font-weight:600; font-variant-numeric:tabular-nums; }
#brindis { position:fixed; bottom:22px; left:50%; transform:translateX(-50%); background:var(--tinta);
  color:#fff; padding:11px 18px; border-radius:9px; font-size:13.5px; opacity:0; transition:opacity .2s;
  pointer-events:none; z-index:20; max-width:80vw; }
#brindis.ver { opacity:1; }
.nav { display:flex; gap:6px; margin-bottom:14px; }
.nav a { text-decoration:none; color:var(--suave); font-size:13px; font-weight:600; padding:6px 12px;
  border-radius:7px; display:inline-flex; align-items:center; gap:7px; }
.nav a.activo { background:var(--tinta); color:#fff; }
.nav .badge { background:var(--aviso); color:#fff; font-size:11px; padding:1px 7px; border-radius:999px; }
.nav a.activo .badge { background:#fff; color:var(--tinta); }
.grupo { margin-bottom:22px; background:#fff; border:1px solid var(--linea); border-radius:11px;
  overflow:hidden; }
.grupo .cab { display:flex; align-items:center; gap:11px; padding:12px 16px;
  border-bottom:1px solid var(--linea); }
.grupo .cab h2 { margin:0; font-size:15px; }
.cand-cola { display:grid; grid-template-columns:64px 1fr auto auto auto; gap:12px; align-items:center;
  padding:11px 16px; border-bottom:1px solid var(--linea); }
.cand-cola:last-child { border-bottom:none; }
.cand-cola img { width:64px; height:64px; object-fit:contain; background:#fff; border:1px solid var(--linea);
  border-radius:6px; }
.cand-cola .desc .n { font-size:13.5px; line-height:1.35; }
.cand-cola .desc .ped { font-size:12px; margin-top:3px; color:#334155; }
.cand-cola .desc .ped b { color:#0f172a; }
.cand-cola .desc .m { font-size:11.5px; color:var(--suave); margin-top:2px; }
.cand-cola .desc .m .isbn { font-size:11px; background:#f1f5f9; padding:1px 5px;
  border-radius:5px; color:#475569; }
.cand-cola .p { font-size:16px; font-weight:600; font-variant-numeric:tabular-nums; }
.cand-cola select { font:inherit; padding:6px 9px; border:1px solid var(--linea); border-radius:7px; }
.cand-cola .acc { display:flex; gap:6px; }
.vacia { text-align:center; color:var(--suave); padding:60px 20px; }
.vacia b { display:block; font-size:18px; color:var(--tinta); margin-bottom:6px; }
"""


GUION = r"""
const $ = (s, r=document) => r.querySelector(s);
const brindis = $('#brindis');
let tempo;
function avisar(msg, malo=false) {
  brindis.textContent = msg;
  brindis.style.background = malo ? '#b91c1c' : '#16181d';
  brindis.classList.add('ver');
  clearTimeout(tempo);
  tempo = setTimeout(() => brindis.classList.remove('ver'), 3200);
}
async function enviar(ruta, cuerpo) {
  const r = await fetch(ruta, {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(cuerpo)});
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.ok === false) { avisar(d.mensaje || 'No se pudo', true); return null; }
  return d;
}
// Filtro y busqueda, igual que en la vista.
const caja = $('#buscar'), filtro = $('#filtro');
function aplicar() {
  const q = caja.value.toLowerCase().trim(), f = filtro.value;
  document.querySelectorAll('.concepto').forEach(c => {
    const coincide = !q || c.dataset.buscar.includes(q);
    const pasa = f === 'todo'
      || (f === 'sin_producto' && c.dataset.estado === 'vacio')
      || (f === 'huecos' && c.dataset.estado !== 'completo' && c.dataset.tipo === 'util')
      || (f === 'sin_foto' && c.dataset.sinfoto === '1')
      || (f === 'revisar' && c.dataset.revisar === '1');
    c.classList.toggle('oculto', !(coincide && pasa));
  });
}
caja.addEventListener('input', aplicar);
filtro.addEventListener('change', aplicar);

// --- Empaque: corregir unidades_por_empaque sin recargar ---
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-empaque]');
  if (!b) return;
  const cont = b.closest('.empaque');
  const valor = parseInt(cont.querySelector('input').value, 10);
  if (!(valor >= 1)) { avisar('El empaque es un entero >= 1', true); return; }
  const d = await enviar('/empaque', {producto_id: b.dataset.empaque, unidades: valor});
  if (d) avisar('Empaque actualizado.');
});

// --- Descartar: no_comprar o fuera de stock ---
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-descartar]');
  if (!b) return;
  const cid = b.dataset.descartar, nombre = b.dataset.nombre;
  if (!confirm(`Marcar "${nombre}" como no_comprar? No se lo ofreceremos al papa.`)) return;
  const d = await enviar('/descartar', {concepto_id: cid});
  if (d) { avisar('Marcado no_comprar.'); setTimeout(() => location.reload(), 900); }
});

// --- Volcar a CSV ---
$('#volcar').addEventListener('click', async () => {
  if (!confirm('Volcar el catalogo de la base a los CSV curados?')) return;
  const d = await enviar('/volcar', {});
  if (d) avisar(d.mensaje || 'Volcado listo.');
});

// --- Dialogo agregar libro ---
const dlgLibro = $('#dlg-libro');
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-libro]');
  if (!b) return;
  dlgLibro.querySelector('[name=concepto_id]').value = b.dataset.libro;
  dlgLibro.querySelector('.pista').textContent = 'Para ' + b.dataset.nombre;
  dlgLibro.showModal();
});
$('#libro-guardar').addEventListener('click', async (e) => {
  e.preventDefault();
  const f = dlgLibro.querySelector('form');
  const cuerpo = {
    concepto_id: f.concepto_id.value, isbn: f.isbn.value, titulo: f.titulo.value,
    precio: parseInt(f.precio.value, 10), tienda: f.tienda.value, nivel: f.nivel.value,
  };
  const d = await enviar('/libro', cuerpo);
  if (d) { dlgLibro.close(); avisar(d.mensaje); setTimeout(() => location.reload(), 1000); }
});

// --- Dialogo agregar util (asistido por tiendas) ---
const dlgUtil = $('#dlg-util');
let utilConcepto = null;
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-util]');
  if (!b) return;
  utilConcepto = b.dataset.util;
  dlgUtil.querySelector('.pista').textContent = 'Para ' + b.dataset.nombre;
  dlgUtil.querySelector('[name=consulta]').value = b.dataset.consulta || b.dataset.nombre;
  dlgUtil.querySelector('.candidatos').innerHTML = '';
  dlgUtil.showModal();
});
$('#util-buscar').addEventListener('click', async (e) => {
  e.preventDefault();
  const consulta = dlgUtil.querySelector('[name=consulta]').value.trim();
  const cont = dlgUtil.querySelector('.candidatos');
  cont.innerHTML = '<div class="pista">Buscando en Exito, Panamericana y Grancentral...</div>';
  const d = await enviar('/util-buscar', {consulta});
  if (!d) { cont.innerHTML = '<div class="pista">Fallo la busqueda.</div>'; return; }
  if (!d.candidatos.length) {
    cont.innerHTML = '<div class="pista">Ninguna tienda devolvio algo con esa consulta.</div>'; return;
  }
  cont.innerHTML = '';
  d.candidatos.forEach(c => {
    const div = document.createElement('div');
    div.className = 'cand';
    const foto = c.imagen_url ? `<img src="${c.imagen_url}" alt="">`
      : '<div class="sinfoto" style="width:46px;height:46px">-</div>';
    const marca = c.marca ? ' · ' + c.marca : '';
    div.innerHTML = `${foto}
      <div class="info"><div>${c.nombre}</div><div class="meta">${c.tienda}${marca}</div></div>
      <div class="p">$${c.precio.toLocaleString('es-CO')}</div>
      <select class="nivel-cand"><option value="economico">economico</option>
        <option value="confiable" selected>confiable</option>
        <option value="premium">premium</option></select>
      <button class="mini primario">Agregar</button>`;
    div.querySelector('button').addEventListener('click', async () => {
      const nivel = div.querySelector('.nivel-cand').value;
      const r = await enviar('/util', {concepto_id: utilConcepto, slug: c.slug, sku: c.sku, consulta, nivel});
      if (r) { dlgUtil.close(); avisar(r.mensaje); setTimeout(() => location.reload(), 1000); }
    });
    cont.appendChild(div);
  });
});
document.querySelectorAll('[data-cerrar]').forEach(b => b.addEventListener('click', (e) => {
  e.preventDefault(); b.closest('dialog').close();
}));

// --- Editar un producto suelto (nombre, foto, precio, nivel, marca, concepto, atributos) ---
const dlgEd = $('#dlg-editar');
function jsonSeguro(txt, porOmision) {
  try { return JSON.parse(txt); } catch (_) { return porOmision; }
}
function pintarAttrs(claves, valores) {
  // Una casilla por atributo que el concepto declara (color, tamano, hojas...),
  // precargada con lo que el producto ya tiene. Si el producto trae un atributo
  // que el concepto no declara, tambien se muestra para no perderlo al guardar.
  const cont = $('#editar-attrs');
  cont.innerHTML = '';
  const llaves = [...claves];
  Object.keys(valores || {}).forEach(k => { if (!llaves.includes(k)) llaves.push(k); });
  if (!llaves.length) {
    cont.innerHTML = '<em class="pista">Este concepto no declara atributos.</em>'; return;
  }
  llaves.forEach(k => {
    const fila = document.createElement('div');
    fila.className = 'attr-fila';
    const et = document.createElement('label'); et.textContent = k;
    const inp = document.createElement('input'); inp.dataset.attr = k;
    inp.value = valores && valores[k] != null ? valores[k] : '';
    fila.appendChild(et); fila.appendChild(inp); cont.appendChild(fila);
  });
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-editar]');
  if (!b) return;
  const card = b.closest('.prod'), f = dlgEd.querySelector('form');
  f.producto_id.value = card.dataset.pid;
  f.nombre.value = card.dataset.pnombre || '';
  f.imagen_url.value = card.dataset.pimg || '';
  f.precio.value = card.dataset.pprecio || '';
  f.nivel.value = card.dataset.pnivel || 'confiable';
  f.marca.value = card.dataset.pmarca || '';
  if (card.dataset.pconcepto) f.concepto_id.value = card.dataset.pconcepto;
  pintarAttrs(jsonSeguro(card.dataset.pclaves, []), jsonSeguro(card.dataset.pattrs, {}));
  dlgEd.querySelector('.pista').textContent = card.dataset.pnombre || '';
  dlgEd.showModal();
});
$('#editar-guardar').addEventListener('click', async (e) => {
  e.preventDefault();
  const f = dlgEd.querySelector('form');
  const precio = parseInt(f.precio.value, 10);
  const atributos = {};
  $('#editar-attrs').querySelectorAll('input[data-attr]').forEach(inp => {
    const v = inp.value.trim();
    if (v) atributos[inp.dataset.attr] = v;  // vacio = no guardar esa clave
  });
  const cuerpo = {
    producto_id: f.producto_id.value, nombre: f.nombre.value.trim(),
    imagen_url: f.imagen_url.value.trim(), nivel: f.nivel.value,
    precio: Number.isFinite(precio) ? precio : null,
    marca: f.marca.value.trim(), concepto_id: f.concepto_id.value, atributos,
  };
  const d = await enviar('/editar', cuerpo);
  if (d) { dlgEd.close(); avisar(d.mensaje); setTimeout(() => location.reload(), 900); }
});

// --- Quitar (desactivar) un producto duplicado o que no es para ninos ---
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-borrar]');
  if (!b) return;
  const card = b.closest('.prod');
  if (!confirm(`Quitar "${card.dataset.pnombre}" del catalogo?`)) return;
  b.disabled = true;
  const d = await enviar('/borrar', {producto_id: b.dataset.borrar});
  if (d) { avisar(d.mensaje); card.remove(); } else { b.disabled = false; }
});
"""


GUION_COLA = r"""
const $ = (s, r=document) => r.querySelector(s);
const brindis = $('#brindis');
let tempo;
function avisar(msg, malo=false) {
  brindis.textContent = msg;
  brindis.style.background = malo ? '#b91c1c' : '#16181d';
  brindis.classList.add('ver');
  clearTimeout(tempo);
  tempo = setTimeout(() => brindis.classList.remove('ver'), 3000);
}
async function enviar(ruta, cuerpo) {
  const r = await fetch(ruta, {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(cuerpo)});
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.ok === false) { avisar(d.mensaje || 'No se pudo', true); return null; }
  return d;
}
// Quita la fila del DOM; si el grupo queda vacío, quita el grupo entero.
function quitarFila(fila) {
  const grupo = fila.closest('.grupo');
  fila.remove();
  if (grupo && !grupo.querySelector('.cand-cola')) grupo.remove();
  if (!document.querySelector('.cand-cola')) location.reload();
}
document.addEventListener('click', async (e) => {
  const ap = e.target.closest('[data-aprobar]');
  const re = e.target.closest('[data-rechazar]');
  const ns = e.target.closest('[data-nosurtir]');
  if (ap) {
    const fila = ap.closest('.cand-cola');
    const nivel = fila.querySelector('.nivel').value;
    ap.disabled = true;
    const d = await enviar('/cola-aprobar', {id: ap.dataset.aprobar, nivel});
    if (d) { avisar(d.mensaje); quitarFila(fila); } else { ap.disabled = false; }
  } else if (re) {
    const fila = re.closest('.cand-cola');
    re.disabled = true;
    const d = await enviar('/cola-rechazar', {id: re.dataset.rechazar});
    if (d) { avisar(d.mensaje); quitarFila(fila); } else { re.disabled = false; }
  } else if (ns) {
    if (!confirm(`Marcar "${ns.dataset.nombre}" como no_comprar? No se lo ofreceremos al papá `
      + 'y se descartan todos sus candidatos.')) return;
    const d = await enviar('/cola-rechazar', {concepto_id: ns.dataset.nosurtir, no_surtir: true});
    if (d) { avisar(d.mensaje); setTimeout(() => location.reload(), 900); }
  }
});
"""


def _pesos(centavos: int | None) -> str:
    return f"${centavos // 100:,.0f}".replace(",", ".") if centavos else "sin precio"


def _tarjeta(p: dict[str, Any], concepto: dict[str, Any] | None = None) -> str:
    e = html.escape
    foto = (
        f'<img src="{e(p["imagen_url"])}" alt="" loading="lazy">'
        if p["imagen_url"]
        else '<div class="sinfoto">sin foto</div>'
    )
    atributos = p.get("atributos") or {}
    attrs = "".join(f"<code>{e(str(k))}: {e(str(v))}</code>" for k, v in atributos.items())
    personaje = f"<span>🏷️ {e(p['personaje'])}</span>" if p["personaje"] else ""
    marca = f'<span class="marca">{e(p["marca"])}</span>' if p.get("marca") else ""
    nombre = e(p["nombre"])
    enlace = f'<a href="{e(p["url"])}" target="_blank" rel="noopener">{nombre}</a>' if p["url"] else nombre
    empaque_val = p["unidades_por_empaque"] or 1
    precio_pesos = (p["precio"] or 0) // 100  # el dialogo de editar trabaja en pesos
    # El diálogo de editar se llena desde estos data-attributes. `pconcepto` dice
    # en qué concepto está hoy (para preseleccionar el <select> de mover), y
    # `pclaves`/`pattrs` viajan como JSON para pintar una casilla por atributo
    # que el concepto declara, ya precargada con lo que el producto tiene.
    concepto_id = e(concepto["id"]) if concepto else ""
    claves = json.dumps(concepto["atributos_clave"] if concepto else [], ensure_ascii=False)
    return f"""<div class="prod"
      data-pid="{e(p["id"])}" data-pnombre="{e(p["nombre"])}" data-pnivel="{e(p["nivel"])}"
      data-pimg="{e(p["imagen_url"] or "")}" data-pprecio="{precio_pesos}"
      data-pmarca="{e(p.get("marca") or "")}" data-pconcepto="{concepto_id}"
      data-pclaves="{e(claves)}" data-pattrs="{e(json.dumps(atributos, ensure_ascii=False))}">
      {foto}
      <div class="nivel {e(p["nivel"])}">{e(p["nivel"])}</div>
      <div class="nom">{enlace}</div>
      <div class="precio">{_pesos(p["precio"])}</div>
      <div class="meta"><span>{e(p["tienda"] or "sin tienda")}</span>{marca}{personaje}</div>
      <div class="empaque">empaque
        <input type="number" min="1" value="{empaque_val}" title="unidades por empaque">
        <span>{e(p["unidad_base"] or "unidad")}</span>
        <button class="mini" data-empaque="{e(p["id"])}">guardar</button></div>
      <div class="attrs">{attrs or "<em>sin atributos</em>"}</div>
      <div class="prod-acc">
        <button class="mini" data-editar="{e(p["id"])}">Editar</button>
        <button class="mini peligro" data-borrar="{e(p["id"])}">Quitar</button>
      </div>
    </div>"""


def _bloque_concepto(c: dict[str, Any]) -> str:
    e = html.escape
    niveles = {p["nivel"] for p in c["productos"]}
    es_util = c["tipo_item"] == TipoItem.UTIL.value
    if not c["productos"]:
        estado, etiqueta = "vacio", "sin productos"
    elif len(niveles) >= 3:
        estado, etiqueta = "completo", "3 niveles"
    else:
        estado, etiqueta = "parcial", f"{len(niveles)} de 3 niveles"

    por_revisar = any(float(p["quality_score"] or 0) < 0.5 for p in c["productos"])
    sin_foto = any(not p["imagen_url"] for p in c["productos"]) or not c["productos"]
    es_libro = c["tipo_item"] == TipoItem.LIBRO_LIBRE.value
    destacado = es_util and estado != "completo"
    buscar = " ".join(
        [c["nombre"], c["codigo"], *(c["sinonimos"] or []), *(p["nombre"] for p in c["productos"])]
    ).lower()

    pastillas = [f'<span class="pill {estado}">{etiqueta}</span>']
    if es_libro:
        pastillas.append('<span class="pill libro">libro</span>')
    if c["tipo_item"] == TipoItem.NO_COMPRAR.value:
        pastillas.append('<span class="pill vacio">no se surte</span>')
    if por_revisar:
        pastillas.append('<span class="pill parcial">tiene sin revisar</span>')
    pastillas.append(f'<span class="pill">pedido {c["demanda"]}x</span>')

    nombre_attr = e(c["nombre"])
    acciones = (
        f'<button class="mini primario" data-util="{e(c["id"])}" data-nombre="{nombre_attr}" '
        f'data-consulta="{nombre_attr}">+ Útil</button>'
        f'<button class="mini" data-libro="{e(c["id"])}" data-nombre="{nombre_attr}">+ Libro</button>'
        f'<button class="mini peligro" data-descartar="{e(c["id"])}" '
        f'data-nombre="{nombre_attr}">Descartar</button>'
    )
    tarjetas = "".join(_tarjeta(p, c) for p in c["productos"]) or (
        '<div class="prod"><div class="sinfoto">nada que ofrecer todavía</div></div>'
    )
    return f"""<section class="concepto{" destacado" if destacado else ""}" data-estado="{estado}"
      data-tipo="{e(c["tipo_item"])}" data-libro="{1 if es_libro else 0}"
      data-revisar="{1 if por_revisar else 0}" data-sinfoto="{1 if sin_foto else 0}"
      data-buscar="{e(buscar)}">
      <div class="cab"><h2>{e(c["nombre"])}</h2><span class="cod">{e(c["codigo"])}</span>
        {"".join(pastillas)}<div class="acciones">{acciones}</div></div>
      <div class="rejilla">{tarjetas}</div>
    </section>"""


def _opciones_nivel(por_omision: str = "confiable") -> str:
    return "".join(
        f'<option value="{n.value}"{" selected" if n.value == por_omision else ""}>{n.value}</option>'
        for n in Nivel
    )


def _nav(activo: str, por_revisar: int) -> str:
    """Las dos vistas del admin: el catálogo y la cola de revisión."""
    cola = f'Cola de revisión<span class="badge">{por_revisar}</span>' if por_revisar else "Cola de revisión"
    return f"""<nav class="nav">
      <a href="/"{' class="activo"' if activo == "catalogo" else ""}>Catálogo</a>
      <a href="/cola"{' class="activo"' if activo == "cola" else ""}>{cola}</a>
    </nav>"""


def _opciones_concepto(conceptos: list[dict[str, Any]]) -> str:
    """Las opciones del <select> para mover un producto a otro concepto.

    Ordenadas por código para que la lista sea buscable con el teclado, y con el
    código a la vista (C031 · resma) porque hay nombres que se parecen -hojas vs
    resma, marcador vs resaltador- y el código desambigua.
    """
    e = html.escape
    ordenados = sorted(conceptos, key=lambda c: c["codigo"])
    return "".join(
        f'<option value="{e(c["id"])}">{e(c["codigo"])} · {e(c["nombre"])}</option>' for c in ordenados
    )


def construir(conceptos: list[dict[str, Any]], resumen: dict[str, int]) -> str:
    momento = datetime.now(UTC).astimezone().strftime("%d/%m/%Y %H:%M")
    bloques = "".join(_bloque_concepto(c) for c in conceptos)
    opciones_concepto = _opciones_concepto(conceptos)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin · Catálogo Tukit</title><style>{ESTILOS}</style></head>
<body>
<header>
  {_nav("catalogo", resumen.get("por_revisar_cola", 0))}
  <h1>Catálogo Tukit · administración</h1>
  <div class="sub">Deja el catálogo listo antes de que un papá vea nada.
    Estado en vivo desde la base · {momento}</div>
  <div class="cifras">
    <div class="cifra"><b>{resumen["productos"]}</b><span>productos</span></div>
    <div class="cifra"><b>{resumen["comprables"]}</b><span>conceptos comprables</span></div>
    <div class="cifra"><b>{resumen["completos"]}</b><span>con los 3 niveles</span></div>
    <div class="cifra"><b>{resumen["sin_producto"]}</b><span>sin producto</span></div>
    <div class="cifra"><b>{resumen["con_foto"]}</b><span>con foto</span></div>
    <div class="cifra"><b>{resumen["por_revisar"]}</b><span>sin revisar</span></div>
  </div>
</header>
<main>
  <div class="barra">
    <input id="buscar" type="search" placeholder="buscar un útil, una marca, un personaje...">
    <select id="filtro">
      <option value="todo">todo el catálogo</option>
      <option value="huecos">huecos comprables (sin 3 niveles)</option>
      <option value="sin_producto">sin ningún producto</option>
      <option value="sin_foto">sin foto</option>
      <option value="revisar">lo que falta revisar</option>
    </select>
    <button id="volcar" class="primario">Volcar a CSV</button>
  </div>
  {bloques}
</main>

<dialog id="dlg-libro"><div class="cuerpo"><form>
  <h3>Agregar libro</h3><div class="pista"></div>
  <input type="hidden" name="concepto_id">
  <label>ISBN-13</label><input name="isbn" placeholder="9789580000000">
  <label>Título</label><input name="titulo" placeholder="La casa de los espíritus">
  <div class="fila">
    <div><label>Precio (COP)</label><input name="precio" type="number" placeholder="45000"></div>
    <div><label>Tienda</label><select name="tienda"><option value="panamericana">panamericana</option>
      <option value="exito">exito</option><option value="grancentral">grancentral</option></select></div>
    <div><label>Nivel</label><select name="nivel">{_opciones_nivel()}</select></div>
  </div>
  <div class="pie"><button data-cerrar>Cancelar</button>
    <button id="libro-guardar" class="primario">Guardar</button></div>
</form></div></dialog>

<dialog id="dlg-util"><div class="cuerpo"><form>
  <h3>Agregar útil</h3><div class="pista"></div>
  <label>Buscar en las tiendas</label>
  <div class="fila"><input name="consulta" placeholder="tijeras punta roma">
    <button id="util-buscar" class="primario" style="flex:0 0 auto">Buscar</button></div>
  <div class="candidatos"></div>
  <div class="pie"><button data-cerrar>Cerrar</button></div>
</form></div></dialog>

<dialog id="dlg-editar"><div class="cuerpo"><form>
  <h3>Editar producto</h3><div class="pista"></div>
  <input type="hidden" name="producto_id">
  <label>Nombre</label><input name="nombre">
  <label>Foto (URL)</label><input name="imagen_url" placeholder="https://...">
  <div class="fila">
    <div><label>Precio (COP)</label><input name="precio" type="number" placeholder="6500"></div>
    <div><label>Nivel</label><select name="nivel">{_opciones_nivel()}</select></div>
  </div>
  <div class="fila">
    <div><label>Marca</label><input name="marca" placeholder="Faber-Castell"></div>
    <div><label>Concepto</label><select name="concepto_id">{opciones_concepto}</select></div>
  </div>
  <label>Atributos</label>
  <div id="editar-attrs" class="attrs-edit"></div>
  <div class="pie"><button data-cerrar>Cancelar</button>
    <button id="editar-guardar" class="primario">Guardar</button></div>
</form></div></dialog>

<div id="brindis"></div>
<script>{GUION}</script>
</body></html>"""


def _fila_cola(p: dict[str, Any]) -> str:
    e = html.escape
    foto = (
        f'<img src="{e(p["imagen_url"])}" alt="" loading="lazy">'
        if p["imagen_url"]
        else '<div class="sinfoto" style="width:64px;height:64px">-</div>'
    )
    nombre = e(p["nombre"])
    enlace = f'<a href="{e(p["url"])}" target="_blank" rel="noopener">{nombre}</a>' if p["url"] else nombre
    marca = f" · {e(p['marca'])}" if p["marca"] else ""
    # El "sugerido" es lo que pidio el colegio; para un libro es el titulo con
    # el que hay que casar la edicion, asi que va completo y destacado, no
    # recortado a 40 caracteres como una nota al pie. El ISBN, cuando lo hay,
    # es el dato que confirma que es LA edicion: se muestra aparte y monoespaciado.
    sugerido = e(p["texto_origen"] or "")
    ped = f'<div class="ped">pidieron: <b>{sugerido}</b></div>' if sugerido else ""
    isbn = e(p.get("ean") or "")
    isbn_html = f'<code class="isbn">ISBN {isbn}</code>' if isbn else ""
    meta = f"{e(p['tienda'] or 'sin tienda')}{marca}"
    return f"""<div class="cand-cola" data-id="{e(p["id_corto"])}">
      {foto}
      <div class="desc"><div class="n">{enlace}</div>
        {ped}
        <div class="m">{meta} {isbn_html}</div></div>
      <div class="p">{_pesos(p["precio"])}</div>
      <select class="nivel">{_opciones_nivel(p["nivel_sugerido"] or "confiable")}</select>
      <div class="acc">
        <button class="mini primario" data-aprobar="{e(p["id_corto"])}">Aprobar</button>
        <button class="mini peligro" data-rechazar="{e(p["id_corto"])}">Descartar</button>
      </div>
    </div>"""


def _grupo_cola(g: dict[str, Any]) -> str:
    e = html.escape
    cod = f'<span class="cod">{e(g["codigo"])}</span>' if g["codigo"] else ""
    nuevo = '<span class="pill vacio">concepto nuevo</span>' if g["es_nuevo"] else ""
    surtir = (
        f'<button class="mini peligro" data-nosurtir="{e(g["concepto_id"])}" '
        f'data-nombre="{e(g["nombre"])}">No proveemos este concepto</button>'
        if g["concepto_id"]
        else ""
    )
    filas = "".join(_fila_cola(p) for p in g["propuestas"])
    return f"""<section class="grupo">
      <div class="cab"><h2>{e(g["nombre"])}</h2>{cod}{nuevo}
        <span class="pill">pedido {g["demanda"]}x</span>
        <span class="pill">{len(g["propuestas"])} por revisar</span>
        <div style="margin-left:auto">{surtir}</div></div>
      {filas}
    </section>"""


def construir_cola(grupos: list[dict[str, Any]], por_revisar: int) -> str:
    momento = datetime.now(UTC).astimezone().strftime("%d/%m/%Y %H:%M")
    if grupos:
        total = sum(len(g["propuestas"]) for g in grupos)
        cuerpo = (
            f'<div class="sub" style="margin-bottom:18px">{total} candidatos en '
            f"{len(grupos)} conceptos, del más pedido al menos. Aprobar crea el producto; "
            "descartar quita el candidato. «No proveemos» cierra el concepto entero.</div>"
            + "".join(_grupo_cola(g) for g in grupos)
        )
    else:
        cuerpo = (
            '<div class="vacia"><b>La cola está vacía.</b>'
            "Nada pendiente de revisar. Corre <code>make bd-completar</code> para "
            "buscar candidatos de los conceptos con huecos, o agrega a mano desde el catálogo.</div>"
        )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cola · Catálogo Tukit</title><style>{ESTILOS}</style></head>
<body>
<header>
  {_nav("cola", por_revisar)}
  <h1>Cola de revisión</h1>
  <div class="sub">Candidatos que nadie ha mirado todavía. Aprobar es lo que los vuelve
    catálogo. · {momento}</div>
</header>
<main>{cuerpo}</main>
<div id="brindis"></div>
<script>{GUION_COLA}</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Servidor
# ---------------------------------------------------------------------------


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *_a: Any) -> None:  # silencio, no ensuciar la consola
        pass

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str = "application/json") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, dato: dict[str, Any]) -> None:
        self._responder(codigo, json.dumps(dato, ensure_ascii=False).encode("utf-8"))

    def _cuerpo_json(self) -> dict[str, Any]:
        largo = int(self.headers.get("Content-Length") or 0)
        if not largo:
            return {}
        try:
            return json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            conceptos, resumen = asyncio.run(_leer())
            self._responder(200, construir(conceptos, resumen).encode("utf-8"), "text/html")
        elif ruta == "/cola":
            grupos = asyncio.run(_leer_cola())
            total = sum(len(g["propuestas"]) for g in grupos)
            self._responder(200, construir_cola(grupos, total).encode("utf-8"), "text/html")
        else:
            self._json(404, {"ok": False, "mensaje": "no existe"})

    def do_POST(self) -> None:  # noqa: N802
        ruta = urlparse(self.path).path
        cuerpo = self._cuerpo_json()
        try:
            despacho = {
                "/util-buscar": self._util_buscar,
                "/util": self._util,
                "/libro": self._libro,
                "/descartar": self._descartar,
                "/editar": self._editar,
                "/borrar": self._borrar,
                "/empaque": self._empaque,
                "/volcar": self._volcar,
                "/cola-aprobar": self._cola_aprobar,
                "/cola-rechazar": self._cola_rechazar,
            }.get(ruta)
            if despacho is None:
                self._json(404, {"ok": False, "mensaje": "no existe"})
                return
            despacho(cuerpo)
        except Exception as error:  # noqa: BLE001 - un error de curaduria no debe tumbar el servidor
            self._json(500, {"ok": False, "mensaje": f"error: {error}"})

    # -- handlers --

    def _util_buscar(self, cuerpo: dict[str, Any]) -> None:
        consulta = (cuerpo.get("consulta") or "").strip()
        if not consulta:
            self._json(400, {"ok": False, "mensaje": "falta la consulta"})
            return
        candidatos = buscar_candidatos(consulta)
        self._json(
            200,
            {
                "ok": True,
                "candidatos": [
                    {
                        "slug": slug,
                        "sku": o.sku,
                        "nombre": o.nombre[:80],
                        "precio": o.precio_cop,
                        "marca": o.marca,
                        "tienda": slug,
                        "imagen_url": o.imagen_url,
                    }
                    for slug, o in candidatos
                ],
            },
        )

    def _util(self, cuerpo: dict[str, Any]) -> None:
        consulta = (cuerpo.get("consulta") or "").strip()
        slug = cuerpo.get("slug") or ""
        sku = cuerpo.get("sku") or ""
        nivel = cuerpo.get("nivel") or "confiable"
        concepto_id = cuerpo.get("concepto_id") or ""
        # Se vuelve a buscar y se toma la oferta por sku: no confiamos en que el
        # cliente arme la Oferta, solo en que elija cual de las que la tienda
        # devolvio. Asi el precio y la ficha salen de la tienda, no del navegador.
        elegida = next((o for s, o in buscar_candidatos(consulta) if s == slug and o.sku == sku), None)
        if elegida is None:
            self._json(422, {"ok": False, "mensaje": "Ese candidato ya no está disponible; busca de nuevo."})
            return
        ok, mensaje = asyncio.run(agregar_util(concepto_id, slug, elegida, nivel))
        self._json(200 if ok else 422, {"ok": ok, "mensaje": mensaje})

    def _libro(self, cuerpo: dict[str, Any]) -> None:
        try:
            precio = int(cuerpo.get("precio") or 0)
        except (TypeError, ValueError):
            precio = 0
        if precio <= 0:
            self._json(400, {"ok": False, "mensaje": "El precio debe ser un entero positivo en pesos."})
            return
        ok, mensaje = asyncio.run(
            agregar_libro(
                cuerpo.get("concepto_id") or "",
                cuerpo.get("isbn") or "",
                (cuerpo.get("titulo") or "").strip(),
                precio,
                cuerpo.get("tienda") or "panamericana",
                cuerpo.get("nivel") or "confiable",
            )
        )
        self._json(200 if ok else 422, {"ok": ok, "mensaje": mensaje})

    def _descartar(self, cuerpo: dict[str, Any]) -> None:
        concepto_id = cuerpo.get("concepto_id") or ""
        filas = asyncio.run(_fijar_tipo_concepto(concepto_id, TipoItem.NO_COMPRAR.value))
        if not filas:
            self._json(404, {"ok": False, "mensaje": "No encontré ese concepto."})
            return
        self._json(200, {"ok": True, "mensaje": "Concepto marcado no_comprar."})

    def _editar(self, cuerpo: dict[str, Any]) -> None:
        producto_id = (cuerpo.get("producto_id") or "").strip()
        if not producto_id:
            self._json(400, {"ok": False, "mensaje": "falta el producto"})
            return
        precio = cuerpo.get("precio")
        if precio is not None:
            try:
                precio = int(precio) * 100  # el navegador manda pesos; la base guarda centavos
            except (TypeError, ValueError):
                self._json(400, {"ok": False, "mensaje": "El precio debe ser un entero en pesos."})
                return
            if precio <= 0:
                self._json(400, {"ok": False, "mensaje": "El precio debe ser positivo."})
                return
        # marca y atributos van tal cual (cadena vacía / {} son borrados a
        # propósito); concepto_id solo si viene, para no reasignar sin querer.
        atributos = cuerpo.get("atributos")
        if atributos is not None and not isinstance(atributos, dict):
            self._json(400, {"ok": False, "mensaje": "Los atributos deben ser un objeto."})
            return
        ok, mensaje = asyncio.run(
            _editar_producto(
                producto_id,
                nombre=(cuerpo.get("nombre") or "").strip() or None,
                nivel=cuerpo.get("nivel") or None,
                imagen_url=cuerpo.get("imagen_url"),
                precio_centavos=precio,
                marca=cuerpo.get("marca"),
                concepto_id=(cuerpo.get("concepto_id") or "").strip() or None,
                atributos={str(k): str(v) for k, v in atributos.items()} if atributos is not None else None,
            )
        )
        self._json(200 if ok else 404, {"ok": ok, "mensaje": mensaje})

    def _borrar(self, cuerpo: dict[str, Any]) -> None:
        producto_id = (cuerpo.get("producto_id") or "").strip()
        if not producto_id:
            self._json(400, {"ok": False, "mensaje": "falta el producto"})
            return
        ok, mensaje = asyncio.run(_borrar_producto(producto_id))
        self._json(200 if ok else 404, {"ok": ok, "mensaje": mensaje})

    def _empaque(self, cuerpo: dict[str, Any]) -> None:
        try:
            unidades = int(cuerpo.get("unidades") or 0)
        except (TypeError, ValueError):
            unidades = 0
        if unidades < 1:
            self._json(400, {"ok": False, "mensaje": "El empaque es un entero >= 1."})
            return
        filas = asyncio.run(
            _fijar_columna_producto(cuerpo.get("producto_id") or "", unidades_por_empaque=unidades)
        )
        if not filas:
            self._json(404, {"ok": False, "mensaje": "No encontré ese producto."})
            return
        self._json(200, {"ok": True, "mensaje": "Empaque actualizado."})

    def _volcar(self, _cuerpo: dict[str, Any]) -> None:
        asyncio.run(volcar_principal(solo_ensayo=False))
        self._json(200, {"ok": True, "mensaje": "Volcado a CSV listo. Revisa el diff de datos/catalogo/."})

    def _cola_aprobar(self, cuerpo: dict[str, Any]) -> None:
        id_corto = (cuerpo.get("id") or "").strip()
        nivel = cuerpo.get("nivel") or "confiable"
        if not id_corto:
            self._json(400, {"ok": False, "mensaje": "falta el id de la propuesta"})
            return
        ok, mensaje = asyncio.run(aprobar_propuesta(id_corto, nivel))
        self._json(200 if ok else 422, {"ok": ok, "mensaje": mensaje})

    def _cola_rechazar(self, cuerpo: dict[str, Any]) -> None:
        # Dos caminos: descartar un candidato suelto (id de propuesta) o cerrar
        # el concepto entero (no_surtir). El segundo descarta de paso todas las
        # propuestas pendientes de ese concepto, para que la cola no las repita.
        no_surtir = bool(cuerpo.get("no_surtir"))
        if no_surtir:
            concepto_id = (cuerpo.get("concepto_id") or "").strip()
            if not concepto_id:
                self._json(400, {"ok": False, "mensaje": "falta el concepto"})
                return
            ok, mensaje = asyncio.run(_no_surtir_concepto(concepto_id))
            self._json(200 if ok else 422, {"ok": ok, "mensaje": mensaje})
            return
        id_corto = (cuerpo.get("id") or "").strip()
        if not id_corto:
            self._json(400, {"ok": False, "mensaje": "falta el id de la propuesta"})
            return
        ok, mensaje = asyncio.run(rechazar_propuesta(id_corto, None, no_surtir=False))
        self._json(200 if ok else 422, {"ok": ok, "mensaje": mensaje})


def servir(puerto: int, abrir: bool) -> int:
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), _Manejador)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"Admin del catálogo en {url}  (Ctrl-C para parar)")
    if abrir:
        import webbrowser

        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nListo.")
    finally:
        servidor.server_close()
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--puerto", type=int, default=8000)
    analizador.add_argument("--abrir", action="store_true")
    args = analizador.parse_args()
    return servir(args.puerto, args.abrir)


if __name__ == "__main__":
    sys.exit(main())
