"""La superficie de ESCRITURA de la revision de listas, sobre HTTP (ADR 0019).

`descubrir.py` ya tenia toda la maquina de revision, pero como CLI: cada
funcion abre su propio motor y escribe en la consola. La consola de
administracion nueva la maneja por HTTP, asi que aqui vive el mismo trabajo
—listar versiones, abrir la revision de una, editar sus renglones, cerrarla,
clonarla para corregir— expuesto como endpoints que escriben a traves del
motor que el servicio ya tiene abierto (`app.state.motor`), no de uno nuevo por
llamada.

Por que un modulo aparte y no `api.py`: ese archivo declara, en su docstring y
de proposito, que es de SOLO LECTURA. La escritura de catalogo pasa por la cola
de propuestas y por la mano de una persona. Estas rutas son justamente esa mano
—la persona que revisa— y separarlas deja esa promesa intacta y la escritura
auditable en un solo sitio.

La puerta que `descubrir` cuida vale igual aqui: una version YA revisada no se
edita ni reabre. La decision es la misma funcion (`_exigir_sin_revisar`), no una
copia. El SQL vive en `repositorios/admin.RepoAdmin`; los guards e shapers
puros en `dominio/listas`; este modulo ata la conexion, cuida las transacciones
y traduce a `ErrorDominio` (ADR 0019).
"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy.exc import IntegrityError
from tukit_comun.http import ErrorDominio

from ..descubrir import atributos_al_aprobar, atributos_verificados, clasificar
from ..dominio.listas import (
    _cuidar_invariantes,
    _exigir_sin_revisar,
    _item_publico,
    _pagina_percepcion,
)
from ..modelos.base import ModoAdquisicion, TipoItem, UnidadBase
from ..repositorios.admin import RepoAdmin

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# Las tiendas con busqueda en vivo (VTEX/Shopify), las mismas que usa `admin`.
_SLUGS_TIENDA = {"exito", "panamericana", "grancentral"}

# El mismo corte que usa el cargador de listas (UMBRAL_CONCEPTO): por debajo, el
# renglon queda sin concepto y va a revision en vez de forzarse al mas parecido.
UMBRAL_CONCEPTO = 0.5

_TIPOS_ITEM = {t.value for t in TipoItem}
_MODOS = {m.value for m in ModoAdquisicion}
_UNIDADES = {u.value for u in UnidadBase}


def _media_type_documento(datos: bytes) -> str:
    """El Content-Type del documento por sus primeros bytes (magic number).

    La subida acepta PDF/JPG/PNG/WEBP y `tarea_importacion.documento` no guarda
    el tipo; se deduce aqui para no servir una imagen como `application/pdf`.
    """
    if datos.startswith(b"%PDF"):
        return "application/pdf"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _motor() -> Any:
    from ..api import app

    return app.state.motor


async def _concepto_id(repo: RepoAdmin, codigo: str) -> uuid.UUID:
    cid = await repo.concepto_id_por_codigo(codigo)
    if cid is None:
        raise ErrorDominio(
            "concepto_no_existe", f"No existe el concepto {codigo}.", estado=422, campo="concepto_codigo"
        )
    return cid


# ---------------------------------------------------------------------------
# Listar versiones y abrir una para revisar
# ---------------------------------------------------------------------------


@router.get("/listas", summary="Versiones de lista y su estado de revision, filtrables")
async def listar_versiones(
    revisada: Annotated[bool | None, Query(description="Solo revisadas o solo sin revisar")] = None,
    colegio_id: Annotated[uuid.UUID | None, Query()] = None,
    grado: Annotated[str | None, Query()] = None,
    anio_lectivo: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> dict[str, Any]:
    """La ultima version de cada lista, no solo la publicada al acudiente.

    Es la version de administracion de `/v1/listas`: aquella filtra a lista
    activa y a la VIGENTE; aqui interesa el estado de revision para decidir que
    curar. Se apoya en la version de NUMERO MAYOR de cada lista (una sola, por
    `uq_version_lista_numero`), no en la vigente: al editar, el borrador nace
    sin vigencia pero con numero mayor, y es justo el que hay que revisar en la
    cola —mientras el acudiente sigue viendo la vigente publicada.
    """
    async with _motor().engine.begin() as conexion:
        filas = await RepoAdmin(conexion).listar_versiones(
            revisada=revisada, colegio_id=colegio_id, grado=grado, anio_lectivo=anio_lectivo
        )
        datos = [
            {
                "lista_id": str(f.lista_id),
                "version_id": str(f.version_id),
                "colegio_id": str(f.colegio_id),
                "grado": f.grado,
                "anio_lectivo": int(f.anio_lectivo),
                "numero": int(f.numero),
                "revisada": f.revisada_en is not None,
                "items": int(f.renglones),
                # De donde vino esta version: 'onboarding' (la envio el colegio o
                # un administrador la subio) o 'sugerencia_padre' (un acudiente la
                # subio y espera). None cuando la version no nacio de una
                # importacion con contexto.
                "procedencia": f.procedencia,
                # Si hay un acudiente detras a quien avisar al aprobar. Nunca el
                # correo: solo el hecho de que exista una referencia.
                "tiene_contacto": f.contacto_referencia is not None,
                # El nombre del colegio NUEVO cuando aun no existe en Tukit, para
                # que la cola lo muestre en vez del id derivado. None si es un
                # colegio aliado (su nombre ya vive en la tabla `colegio`).
                "colegio_nombre": ((f.colegio_datos or {}).get("nombre") if f.colegio_datos else None),
            }
            for f in filas
        ]
    return {"total": len(datos), "listas": datos}


def _lo_que_se_exige(fila: Any, reglas: dict[str, tuple[tuple[str, ...], bool, str]]) -> dict[str, Any]:
    """Lo que la ruta rapida le exigiria a este renglon, separado por origen.

    Para que el revisor cure los atributos en la pantalla y no en el CSV:
    `atributos_leidos` es lo que se lee del texto (la misma regla de
    `_renglon_resuelto`), `atributos` (ya en el renglon) lo curado, y
    `atributos_exigidos` el resultado. `atributos_discriminantes` dice que
    claves se pueden curar: las que filtran en el concepto asignado.
    """
    discriminantes = reglas.get(fila.concepto_codigo, _SIN_REGLAS)[0] if fila.concepto_codigo else ()
    if not discriminantes:
        return {
            "atributos_discriminantes": [],
            "atributos_leidos": {},
            "atributos_exigidos": {},
            "atributos_por_revisar": [],
            "atributos_deducidos": [],
        }
    leidos, por_revisar, juego_inferido = _lo_que_dice_el_texto(
        fila.texto_original, discriminantes, int(fila.cantidad)
    )
    return {
        "atributos_discriminantes": list(discriminantes),
        "atributos_leidos": leidos,
        "atributos_exigidos": _con_lo_curado(leidos, dict(fila.atributos or {}), discriminantes),
        "atributos_por_revisar": por_revisar,
        # Lo leido que el texto no dijo: el `unidades=2` de `caja de...` o de un
        # plural con cantidad uno. La ruta rapida lo suelta si ningun juego
        # cumple, y el revisor tiene que saber que no lo escribio el colegio.
        "atributos_deducidos": ["unidades"] if juego_inferido else [],
    }


@router.get(
    "/listas/{version_id}/revision",
    summary="Los renglones de una version y sus propuestas pendientes",
)
async def ver_revision(version_id: uuid.UUID) -> dict[str, Any]:
    """La vista que alimenta la region 3: renglones + concepto + candidatos.

    No exige que la version este sin revisar: leerla es legitimo tambien
    despues de cerrada (la pantalla de una lista ya aprobada la usa). Lo que se
    niega es ESCRIBIR sobre una revisada, y eso lo cuidan los endpoints de
    edicion, no este.
    """
    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        cabeza = await repo.version_y_lista(version_id)
        if cabeza is None:
            raise ErrorDominio(
                "version_no_existe",
                "No hay ninguna version con ese identificador.",
                estado=404,
            )
        filas = await repo.items_de_revision(version_id)
        reglas = await repo.reglas_por_codigo(
            sorted({f.concepto_codigo for f in filas if f.concepto_codigo is not None})
        )
        items = [{**_item_publico(f), **_lo_que_se_exige(f, reglas)} for f in filas]

        candidatos = [
            {
                "id": str(p.id),
                "texto_origen": p.texto_origen,
                # La llave FIABLE al renglon: el texto se repite (una lista pide
                # dos cuadernos iguales) y agrupar por texto le colgaba a un
                # renglon los candidatos del otro. `item_lista_id` es 1:1.
                "item_id": None if p.item_lista_id is None else str(p.item_lista_id),
                "nombre": p.nombre,
                "marca": p.marca,
                "imagen_url": p.imagen_url,
                "precio": None if p.precio_centavos is None else int(p.precio_centavos) // 100,
                "nivel_sugerido": p.nivel_sugerido,
                "puntaje": float(p.puntaje),
                "concepto": (
                    {"codigo": p.concepto_codigo, "nombre": p.concepto_nombre}
                    if p.concepto_codigo
                    else {"sugerido": p.concepto_sugerido}
                ),
            }
            for p in await repo.propuestas_pendientes_de_version(version_id)
        ]

        # Los datos del colegio NUEVO que se dara de alta al aprobar (nombre,
        # dane y lo que el revisor complete). None cuando la lista es de un
        # colegio ya aliado: no hay identidad que crear ni que completar.
        colegio_datos = await repo.colegio_datos_de(version_id)

    return {
        "version_id": str(cabeza.id),
        # `lista_id` y `total_items` dan a esta respuesta la MISMA forma que
        # `GET /v1/listas/{lista_id}`, para que el pipeline lea los items de una
        # version explicita (preview de una edicion) por el mismo camino que la
        # vigente, sin ramas por origen.
        "lista_id": str(cabeza.lista_id),
        "colegio_id": str(cabeza.colegio_id),
        "grado": cabeza.grado,
        "anio_lectivo": int(cabeza.anio_lectivo),
        "numero": int(cabeza.numero),
        "revisada": cabeza.revisada_en is not None,
        "total_items": len(items),
        "items": items,
        "propuestas": candidatos,
        "colegio_datos": colegio_datos,
    }


# ---------------------------------------------------------------------------
# La ruta rapida: los renglones resueltos de una version YA revisada con sus
# candidatos curados, keyed por concepto, sin buscar por texto ni recomputar.
# ---------------------------------------------------------------------------


_ORDEN_NIVEL = {"economico": 0, "confiable": 1, "premium": 2}

# Las reglas de un concepto que no aparecio: no filtra, no se junta, es un util.
_SIN_REGLAS: tuple[tuple[str, ...], bool, str] = ((), False, "util")

# Un cuaderno por materia es la norma, no un repetido: marcarlos llenaria la
# revision de avisos que nadie tiene que atender (136 en las 18 listas).
_POR_MATERIA = frozenset({"C001"})


def _palabras(texto: str) -> set[str]:
    from ..enriquecer import _normalizar

    return set(re.findall(r"[a-z0-9]+", _normalizar(texto)))


def _posibles_repetidos(
    filas: list[Any], reglas: dict[str, tuple[tuple[str, ...], bool, str]]
) -> dict[int, int]:
    """`orden -> orden` de los renglones que parecen repetir a uno anterior.

    Solo para lo que NO se junta solo: lo que se gasta (pegante, cinta) y los
    textos (`Gateway B1 Student's Book` escrito dos veces de dos formas). Puede
    ser uno por materia a proposito, asi que no se toca: se avisa, y el
    revisor decide. Dos renglones se parecen si son del mismo concepto, exigen
    los mismos atributos y comparten al menos el 60 % de sus palabras. Sin lo
    de los atributos, `acrilico cian` y `acrilico magenta` salian repetidos:
    se parecen en todo menos en lo unico que importa.
    """
    from ..enriquecer import extraer_atributos

    vistos: dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, set[str]]]] = {}
    salida: dict[int, int] = {}
    for f in filas:
        codigo = f.concepto_codigo
        if codigo is None or codigo in _POR_MATERIA or reglas.get(codigo, _SIN_REGLAS)[1]:
            continue
        if (f.tipo_item or "util") in ("no_comprar", "uniforme", "licencia_digital", "diferido", "otro"):
            continue
        exige = extraer_atributos(f.texto_original, reglas.get(codigo, _SIN_REGLAS)[0])
        clave = (codigo, tuple(sorted((k, str(v)) for k, v in exige.items())))
        palabras = _palabras(f.texto_original)
        for orden, otras in vistos.get(clave, []):
            union = palabras | otras
            if union and len(palabras & otras) / len(union) >= 0.6:
                salida[int(f.orden)] = orden
                break
        vistos.setdefault(clave, []).append((int(f.orden), palabras))
    return salida


async def _productos_por_concepto(repo: RepoAdmin, codigos: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Todos los productos activos de esos conceptos, con su precio vigente.

    Se piden todos de una vez y se agrupan en memoria, para no hacer una
    consulta por renglon (el patron N+1).
    """
    if not codigos:
        return {}
    por_concepto: dict[str, list[dict[str, Any]]] = {}
    for f in await repo.productos_por_conceptos(codigos):
        por_concepto.setdefault(f.concepto_codigo, []).append(
            {
                "id": f.id,
                "sku": f.sku_interno,
                "nombre": f.nombre,
                "nivel": f.nivel,
                "personaje": f.personaje,
                "marca": f.marca,
                "imagen_url": f.imagen_url,
                "unidad_base": f.unidad_base,
                "unidades_por_empaque": int(f.unidades_por_empaque or 1),
                "atributos": dict(f.atributos or {}),
                "precio_cop": None if f.centavos is None else int(f.centavos) // 100,
            }
        )
    return por_concepto


# Lo que convierte un renglon en un pedido de varios: `caja de plumones`,
# `kit de pinceles`. Sin numero, el juego se exige como "mas de uno".
_PIDE_UN_JUEGO = re.compile(r"\b(?:cajas?|estuches?|paquetes?|set|kit|juegos?)\b")
# Lo que describe una pieza suelta y no un juego: en `kit de 12 pinceles
# delgados, planos y redondos` ningun pincel es los tres.
_DE_LA_PIEZA = ("grosor", "forma")
# El valor que un revisor pone en la curaduria para que un atributo leido del
# texto NO se exija (`15 hojas de cartulina` en la receta de una bitacora).
NO_EXIGIR = "*"


def _lo_que_dice_el_texto(
    texto: str, discriminantes: tuple[str, ...], cantidad: int = 1
) -> tuple[dict[str, Any], list[str], bool]:
    """Lo que el TEXTO del renglon exige, antes de la curaduria.

    Devuelve los atributos leidos, los que el renglon nombra con varios valores
    (no se exigen; se avisan) y si el `unidades=2` se dedujo en vez de leerse.
    Es la mitad de `_renglon_resuelto` que no mira productos, aparte para que
    la revision de la lista le muestre al revisor exactamente lo que la ruta
    rapida leeria, por la misma regla y no por una copia.
    """
    from ..consulta import _NO_SE_EXIGEN
    from ..enriquecer import _normalizar, atributos_ambiguos, extraer_atributos

    impuestos = {
        k: v for k, v in extraer_atributos(texto, discriminantes).items() if (k, v) not in _NO_SE_EXIGEN
    }
    por_revisar = [a for a in atributos_ambiguos(texto, discriminantes) if a not in impuestos]
    juego_inferido = False
    if "unidades" in discriminantes:
        plano = _normalizar(texto)
        primera = plano.split()[0] if plano.split() else ""
        if impuestos.get("unidades"):
            # Un juego de piezas distintas (`delgados, planos, redondos y
            # abanico`): lo que describe cada pieza no se le exige al juego.
            # En uno de piezas iguales (`colores x 12 triangulares gruesos`)
            # si se exige.
            if por_revisar:
                for atributo in _DE_LA_PIEZA:
                    if impuestos.pop(atributo, None) is not None:
                        por_revisar.append(atributo)
        elif _PIDE_UN_JUEGO.search(plano) or (cantidad == 1 and primera.endswith("s")):
            # `caja de plumones`, o `marcadores` con cantidad uno: mas de uno,
            # aunque no diga cuantos. Sin esto ganaba un Sharpie suelto.
            impuestos["unidades"] = 2
            juego_inferido = True
    return impuestos, por_revisar, juego_inferido


def _con_lo_curado(
    leidos: dict[str, Any], curados: dict[str, Any], discriminantes: tuple[str, ...]
) -> dict[str, Any]:
    """Lo leido del texto con la curaduria encima: lo curado manda, `*` lo quita.

    Una clave curada que no es discriminante del concepto no filtra (puede
    quedar de un concepto anterior del renglon) y un valor vacio no afirma nada.
    """
    impuestos = dict(leidos)
    for k, v in curados.items():
        if k not in discriminantes or v in (None, ""):
            continue
        if v == NO_EXIGIR:
            impuestos.pop(k, None)
        else:
            impuestos[k] = v
    return impuestos


# Lo que un renglon de cierto concepto quiere aunque no lo diga: un `lapiz` a
# secas es negro. Sin esto, «lapices» se resolvia con el lapiz rojo, que es el
# mas barato. Si ningun producto lo cumple, no se exige.
_POR_OMISION: dict[str, dict[str, str]] = {"C002": {"color": "negro"}}

# Lo que se exige solo si algun producto que cumple lo demas lo declara. El
# tamano del cuaderno: «cuaderno grande» recibia un Finlandek de $5.990 que no
# dice ser grande habiendo la version grande (auditoria v4, 23 renglones), pero
# exigirlo siempre dejaba en hueco los cosidos grandes, que ningun cuaderno del
# catalogo declara. No es discriminante del concepto: no se exige a ciegas.
_BLANDOS: dict[str, tuple[str, ...]] = {"C001": ("tamano",)}


def _lo_blando(texto: str, curados: dict[str, Any], concepto: str | None) -> dict[str, Any]:
    """Lo que el renglon pide de los atributos blandos de su concepto, con la curaduria encima."""
    from ..enriquecer import extraer_atributos

    blandos = _BLANDOS.get(concepto or "", ())
    if not blandos:
        return {}
    pide = extraer_atributos(texto, blandos)
    for k in blandos:
        v = curados.get(k)
        if v == NO_EXIGIR:
            pide.pop(k, None)
        elif v not in (None, ""):
            pide[k] = v
    return pide


def _variante_especial(atributo: str, valor: Any) -> bool:
    """Si este valor solo le sirve a quien lo pidio por nombre.

    Una cartulina fluorescente, un cuaderno de cuadros de 1 cm, un micropunta o
    un sketchbook son variantes: el renglon que no las nombra quiere la
    corriente. Sin esto, la variante mas barata se llevaba los renglones
    genericos («cartulina arte por octavos» recibia la fluorescente).
    """
    texto = str(valor).lower()
    if atributo == "acabado":
        return True
    if atributo == "rayado":
        return any(c.isdigit() for c in texto) or texto.startswith("cuadricula ")
    return (atributo, texto) in {("punta", "micropunta"), ("tipo", "dibujo")}


def _sin_variantes_no_pedidas(
    productos: list[dict[str, Any]], impuestos: dict[str, Any], discriminantes: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Los productos sin variantes especiales que el renglon no pidio, o todos si no queda ninguno."""
    corrientes = [
        p
        for p in productos
        if not any(
            k in discriminantes and k not in impuestos and _variante_especial(k, v)
            for k, v in (p.get("atributos") or {}).items()
        )
    ]
    return corrientes or productos


def _renglon_resuelto(
    texto: str,
    curados: dict[str, Any],
    productos: list[dict[str, Any]],
    discriminantes: tuple[str, ...],
    cantidad: int = 1,
    concepto: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Los candidatos de UN renglon, lo que el renglon exige y lo que hay que revisar.

    Antes los candidatos eran del concepto, no del renglon: uno por nivel, tres
    a lo sumo, todos marcados `cumple` porque "la lista ya esta revisada". Pero
    revisar la lista decide el CONCEPTO, no el producto: `Pinturas acrilicas:
    blanco` y `: negro` son el mismo concepto y recibian el mismo oleo magenta,
    y un concepto con cuarenta cuadernos solo le mostraba tres al kit.

    Ahora, con la misma regla que `emparejar`:

    - Se exige lo que el renglon dice de los atributos discriminantes de su
      concepto. Lo que el revisor corrigio en la curaduria (`atributos` del
      item) manda sobre lo que se leyo del texto.
    - Entran TODOS los productos que lo cumplen, no uno por nivel: el
      optimizador elige entre ellos (Ahorrador el mas barato; Premium el de
      mejor nivel y, dentro de el, el mas barato).
    - Sin personaje: el canonico no tiene un acudiente que lo haya pedido. Un
      producto con personaje entra solo si es el unico que cumple, porque
      mejor un cuaderno de Cars que cumple que un hueco.
    - Si nada cumple, no hay candidatos: es un hueco, no un sustituto.

    Lo que el renglon nombra con varios valores (`rayado o cuadriculado`) no
    se exige y se devuelve aparte para que una persona lo mire.
    """
    from ..consulta import _cumple

    leidos, por_revisar, juego_inferido = _lo_que_dice_el_texto(texto, discriminantes, cantidad)
    impuestos = _con_lo_curado(leidos, curados, discriminantes)

    que_cumplen = [p for p in productos if _cumple(p, impuestos)]
    if not que_cumplen and juego_inferido and impuestos.get("unidades") == 2:
        # Lo de "mas de uno" se dedujo, el renglon no lo dijo: si ningun juego
        # cumple, vale la pieza suelta (`Pinceles de punta redonda`, 3#88).
        del impuestos["unidades"]
        que_cumplen = [p for p in productos if _cumple(p, impuestos)]
    por_omision = {
        k: v
        for k, v in _POR_OMISION.get(concepto or "", {}).items()
        if k in discriminantes and k not in impuestos
    }
    if por_omision:
        con_omision = [p for p in que_cumplen if _cumple(p, por_omision)]
        que_cumplen = con_omision or que_cumplen
    blandos = _lo_blando(texto, curados, concepto)
    if blandos:
        con_blandos = [p for p in que_cumplen if _cumple(p, blandos)]
        que_cumplen = con_blandos or que_cumplen
    que_cumplen = _sin_variantes_no_pedidas(que_cumplen, impuestos, discriminantes)
    elegibles = [p for p in que_cumplen if not p.get("personaje")] or que_cumplen
    elegibles.sort(
        key=lambda p: (
            _ORDEN_NIVEL.get(p["nivel"] or "", 9),
            p["precio_cop"] is None,
            p["precio_cop"] or 0,
            p["sku"],
        )
    )

    candidatos = [
        {
            "producto_id": None if p.get("id") is None else str(p["id"]),
            "sku": p.get("sku") or "",
            "nombre": p.get("nombre") or "",
            "nivel": p.get("nivel") or "confiable",
            "marca": p.get("marca"),
            "personaje": p.get("personaje"),
            "imagen_url": p.get("imagen_url"),
            "unidad_base": p.get("unidad_base") or "unidad",
            "unidades_por_empaque": int(p.get("unidades_por_empaque") or 1),
            "atributos": dict(p.get("atributos") or {}),
            "precio_cop": p.get("precio_cop"),
            "cumple": True,
        }
        for p in elegibles
    ]
    return candidatos, impuestos, por_revisar


async def _renglones_resueltos(repo: RepoAdmin, version_id: uuid.UUID) -> list[dict[str, Any]]:
    """Cada renglon de la version con sus candidatos, lo que exige y sus avisos."""
    filas = await repo.items_resueltos(version_id)

    codigos = sorted({f.concepto_codigo for f in filas if f.concepto_codigo is not None})
    productos = await _productos_por_concepto(repo, codigos)
    reglas = await repo.reglas_por_codigo(codigos)
    return armar_items(filas, productos, reglas)


def armar_items(
    filas: list[Any],
    productos: dict[str, list[dict[str, Any]]],
    reglas: dict[str, tuple[tuple[str, ...], bool, str]],
) -> list[dict[str, Any]]:
    """Los renglones de una version, ya resueltos, a partir de lo leido de la base.

    Es la parte de `_renglones_resueltos` que no consulta nada, separada para
    poder correrla sobre `datos/` sin base (`ensayos/kits_offline.py`).
    """
    repetidos = _posibles_repetidos(filas, reglas)

    items = []
    for f in filas:
        candidatos: list[dict[str, Any]] = []
        impuestos: dict[str, Any] = {}
        por_revisar: list[str] = []
        if f.concepto_codigo is not None:
            candidatos, impuestos, por_revisar = _renglon_resuelto(
                f.texto_original,
                dict(f.atributos or {}),
                productos.get(f.concepto_codigo, []),
                reglas.get(f.concepto_codigo, _SIN_REGLAS)[0],
                int(f.cantidad),
                f.concepto_codigo,
            )
        items.append(
            {
                "item_id": str(f.id),
                "orden": int(f.orden),
                "texto_original": f.texto_original,
                "cantidad": int(f.cantidad),
                # Nulo en el renglon significa "lo que diga el concepto", no
                # `util`: es la regla de `routers/catalogo.py`. Sin caer al del
                # concepto, la ruta rapida recibia `util` para una muda de ropa
                # o un uniforme y los mostraba como "No lo tenemos".
                "tipo_item": f.tipo_item or reglas.get(f.concepto_codigo, _SIN_REGLAS)[2],
                "modo_adquisicion": f.modo_adquisicion,
                "concepto_codigo": f.concepto_codigo,
                "concepto_nombre": f.concepto_nombre,
                "instruccion_colegio": f.instruccion_colegio,
                "url_externa": f.url_externa,
                "candidatos": candidatos,
                "atributos_impuestos": impuestos,
                "atributos_por_revisar": por_revisar,
                "uno_por_estudiante": reglas.get(f.concepto_codigo, _SIN_REGLAS)[1],
                "posible_repetido_de": repetidos.get(int(f.orden)),
                "tipo_concepto": reglas.get(f.concepto_codigo, _SIN_REGLAS)[2],
                "avisos_descartados": list(f.avisos_descartados or ()),
            }
        )
    _un_producto_por_herramienta(items)
    return items


def _un_producto_por_herramienta(items: list[dict[str, Any]]) -> None:
    """Que la herramienta pedida en varias materias salga del mismo producto.

    `juntar_herramientas` compra una sola vez lo que un hijo pide repetido,
    pero junta por producto: si `compas` y `compas de precision` eligen dos
    compases distintos, compra los dos (3#35 y 3#47, $59.600 de mas en los
    Ahorradores). Aqui, antes de elegir, cada renglon de un concepto
    uno-por-estudiante se queda con los candidatos que sirven para TODOS los
    renglones de ese concepto: el compas de precision sirve para los dos. Si
    no hay ninguno comun (`regla` y `regla de acero`, sin regla de acero), cada
    renglon conserva los suyos.
    """
    grupos: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item["uno_por_estudiante"] and item["candidatos"]:
            grupos.setdefault(item["concepto_codigo"], []).append(item)
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        comunes = set.intersection(*({c["sku"] for c in i["candidatos"]} for i in grupo))
        if not comunes:
            continue
        for item in grupo:
            item["candidatos"] = [c for c in item["candidatos"] if c["sku"] in comunes]


@router.get(
    "/listas/{version_id}/resueltos",
    summary="Los renglones de una version YA revisada con sus candidatos curados (ruta rapida)",
)
async def resueltos_de_version(version_id: uuid.UUID) -> dict[str, Any]:
    """La fuente de datos de la ruta rapida del acudiente.

    Solo aplica a una version REVISADA: la percepcion ya fue curada por una
    persona, asi que cada renglon ya tiene su concepto decidido y basta con
    traer los candidatos curados de ese concepto —sin salir a las tiendas, sin
    volver a clasificar el texto, sin tocar Gemini—. Un renglon sin concepto
    (compra directa al colegio, no surtible) es una linea informativa: se
    muestra con sus candidatos vacios.

    404 si la version no existe; 409 (`lista_no_revisada`) si aun no fue
    revisada, porque la ruta rapida solo vale sobre listas verificadas. No toca
    `revisada_en`: leer no aprueba.
    """
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        if cabeza is None:
            raise ErrorDominio(
                "version_no_existe",
                "No hay ninguna version con ese identificador.",
                estado=404,
            )
        if cabeza.revisada_en is None:
            raise ErrorDominio(
                "lista_no_revisada",
                "Esa version no ha sido revisada. La ruta rapida solo aplica a listas verificadas.",
                estado=409,
            )

        items = [
            {k: v for k, v in i.items() if k not in ("tipo_concepto", "avisos_descartados")}
            for i in await _renglones_resueltos(repo, version_id)
        ]
    return {
        "version_id": str(cabeza.id),
        "revisada": True,
        "colegio_id": str(cabeza.colegio_id),
        "grado": cabeza.grado,
        "anio_lectivo": int(cabeza.anio_lectivo),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Importar una lista desde onboarding (la escribe inteligencia)
# ---------------------------------------------------------------------------


@router.post(
    "/listas/importar",
    status_code=201,
    summary="Escribir una lista percibida como version SIN revisar, con su evidencia",
)
async def importar_lista(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """El destino de escritura del onboarding: inteligencia percibe, esto guarda.

    Nace SIN revisar a proposito. La percepcion es una hipotesis, no una lista
    aprobada: un administrador la cura contra el documento (que se guarda como
    evidencia) antes de que salga al acudiente. Por eso `revisada_en` queda en
    None y el auto-publicado no existe aqui —la puerta HITL es real.

    Los renglones se resuelven a concepto con el mismo `clasificar` del CLI; el
    que no llega al umbral queda sin concepto y marcado a revision, en vez de
    forzarse al mas parecido. La evidencia (PDF + percepcion cruda) se guarda en
    una `tarea_importacion` completada, no en la version, porque es un hecho del
    proceso de importacion y no del contenido publicado.

    Con `clave_idempotencia` el POST se puede reintentar (ADR 0040): si ya entro
    una importacion con esa clave, se responde con ella, el mismo cuerpo, y no
    se crea otra version. Es lo que hace seguro el reintento de inteligencia
    cuando la respuesta de un intento que si entro se perdio. Sin clave, cada
    POST es una version nueva, como siempre.
    """
    try:
        colegio_id = uuid.UUID(str(cuerpo["colegio_id"]))
        grado = str(cuerpo["grado"])
        anio_lectivo = int(cuerpo["anio_lectivo"])
        items = list(cuerpo["items"])
        evidencia = dict(cuerpo["evidencia"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ErrorDominio(
            "cuerpo_invalido", "Falta o es invalido un campo del cuerpo de importacion.", estado=422
        ) from exc

    try:
        documento = base64.b64decode(str(evidencia["documento_base64"]), validate=True)
    except (KeyError, binascii.Error, ValueError) as exc:
        raise ErrorDominio(
            "documento_invalido",
            "La evidencia no trae un documento en base64 valido.",
            estado=422,
            campo="documento_base64",
        ) from exc
    percepcion_cruda = list(evidencia.get("percepcion_cruda") or [])

    # De quien vino la subida, para que la cola la atribuya bien: 'onboarding'
    # (el colegio o un administrador) o 'sugerencia_padre' (un acudiente). Por
    # omision onboarding, que es el caso historico; cualquier otro valor se
    # rechaza sin adivinar.
    origen = str(cuerpo.get("origen") or "onboarding")
    if origen not in ("onboarding", "sugerencia_padre"):
        raise ErrorDominio(
            "origen_invalido",
            "El origen de la importacion tiene que ser 'onboarding' o 'sugerencia_padre'.",
            estado=422,
            campo="origen",
        )

    # Traza opcional al padre que espera esta lista: cuando un acudiente sube su
    # PDF, la importacion queda ligada a su `usuario_id` (nunca su correo ni
    # telefono, que son PII de Identidad) para poder avisarle cuando un
    # administrador apruebe la version. El onboarding del colegio no trae padre,
    # asi que la referencia queda en None.
    referencia_cruda = cuerpo.get("contacto_referencia")
    try:
        contacto_referencia = uuid.UUID(str(referencia_cruda)) if referencia_cruda is not None else None
    except (ValueError, TypeError) as exc:
        raise ErrorDominio(
            "contacto_invalido",
            "El contacto de referencia no es un identificador valido.",
            estado=422,
            campo="contacto_referencia",
        ) from exc

    # Las preferencias que el padre declaro al subir (paso 3): se guardan tal
    # cual para que el kit de la aprobacion las use. Es dato de negocio, un
    # objeto JSON (pesos, disposicion, personaje_por_hijo); si viene algo que no
    # es objeto se rechaza sin adivinar. El onboarding del colegio no las trae.
    preferencias_crudas = cuerpo.get("preferencias")
    if preferencias_crudas is not None and not isinstance(preferencias_crudas, dict):
        raise ErrorDominio(
            "preferencias_invalidas",
            "Las preferencias tienen que ser un objeto.",
            estado=422,
            campo="preferencias",
        )
    preferencias = preferencias_crudas or None

    # Los datos del colegio cuando la lista viene por un colegio que aun no
    # existe en Tukit: el acudiente lo eligio del directorio de Bogota (trae
    # DANE) o lo escribio a mano (solo nombre). Es un objeto JSON (nombre, dane,
    # y lo que el revisor complete despues); si viene algo que no es objeto se
    # rechaza sin adivinar. Un colegio aliado ya conocido no lo trae.
    colegio_datos_crudos = cuerpo.get("colegio_datos")
    if colegio_datos_crudos is not None and not isinstance(colegio_datos_crudos, dict):
        raise ErrorDominio(
            "colegio_datos_invalidos",
            "Los datos del colegio tienen que ser un objeto.",
            estado=422,
            campo="colegio_datos",
        )
    colegio_datos = colegio_datos_crudos or None

    clave_cruda = cuerpo.get("clave_idempotencia")
    try:
        clave_idempotencia = uuid.UUID(str(clave_cruda)) if clave_cruda is not None else None
    except (ValueError, TypeError) as exc:
        raise ErrorDominio(
            "clave_invalida",
            "La clave de idempotencia no es un identificador valido.",
            estado=422,
            campo="clave_idempotencia",
        ) from exc

    # Se validan TODOS los renglones antes de escribir nada, y el mensaje no
    # repite el texto del renglon: el documento puede traer nombres de menores y
    # un error no debe filtrarlos de vuelta al cliente.
    renglones: list[dict[str, Any]] = []
    for indice, it in enumerate(items):
        try:
            texto = str(it["texto_original"])
        except (KeyError, TypeError) as exc:
            raise ErrorDominio(
                "item_invalido",
                f"El renglon en la posicion {indice} no trae texto_original.",
                estado=422,
                campo="texto_original",
            ) from exc
        cruda = it.get("cantidad")
        cantidad = 1 if cruda is None else int(cruda)
        if cantidad <= 0:
            raise ErrorDominio(
                "cantidad_invalida",
                f"El renglon en la posicion {indice} tiene una cantidad que no es mayor que cero.",
                estado=422,
                campo="cantidad",
            )
        confianza = it.get("confianza")
        renglones.append({"texto": texto, "cantidad": cantidad, "confianza": confianza})

    if clave_idempotencia is not None:
        async with _motor().sesion() as db:
            ya_importada = await RepoAdmin(await db.connection()).importacion_por_clave(clave_idempotencia)
        if ya_importada is not None:
            return ya_importada

    try:
        return await _escribir_importacion(
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
            renglones=renglones,
            origen=origen,
            contacto_referencia=contacto_referencia,
            preferencias=preferencias,
            colegio_datos=colegio_datos,
            documento=documento,
            percepcion_cruda=percepcion_cruda,
            clave_idempotencia=clave_idempotencia,
        )
    except IntegrityError:
        # Dos intentos con la misma clave entraron a la vez y los dos miraron
        # antes de que el otro escribiera. El indice unico frena al segundo y
        # su transaccion entera (version y renglones incluidos) se deshace: se
        # responde con la del primero.
        if clave_idempotencia is None:
            raise
        async with _motor().sesion() as db:
            ya_importada = await RepoAdmin(await db.connection()).importacion_por_clave(clave_idempotencia)
        if ya_importada is None:
            raise
        return ya_importada


async def _escribir_importacion(
    *,
    colegio_id: uuid.UUID,
    grado: str,
    anio_lectivo: int,
    renglones: list[dict[str, Any]],
    origen: str,
    contacto_referencia: uuid.UUID | None,
    preferencias: dict[str, Any] | None,
    colegio_datos: dict[str, Any] | None,
    documento: bytes,
    percepcion_cruda: list[Any],
    clave_idempotencia: uuid.UUID | None,
) -> dict[str, Any]:
    """La escritura de `importar_lista`, en una sola transaccion."""
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())

        # Resolver o crear la lista para (colegio, grado, ano). El indice unico
        # de la lista incluye sede_id; onboarding no la maneja, asi que va NULL.
        lista = await repo.lista_por_llave(colegio_id, grado, anio_lectivo)
        if lista is None:
            lista_id = uuid.uuid4()
            await repo.crear_lista(lista_id, colegio_id, grado, anio_lectivo)
        else:
            lista_id = lista.id

        # El siguiente numero, y quitarle la vigencia a la anterior ANTES de
        # insertar la nueva, para no violar el indice de una sola vigente.
        numero = await repo.max_numero_version(lista_id) + 1
        await repo.desvigar_versiones(lista_id)
        version_id = uuid.uuid4()
        await repo.crear_version(version_id, lista_id, numero, vigente=True)

        conceptos = await repo.cargar_conceptos()
        for orden, renglon in enumerate(renglones, start=1):
            concepto_id, _nombre, parecido = clasificar(renglon["texto"], conceptos)
            if parecido < UMBRAL_CONCEPTO:
                concepto_id = None
            await repo.crear_item(
                id=uuid.uuid4(),
                version_id=version_id,
                orden=orden,
                texto_original=renglon["texto"],
                concepto_id=concepto_id,
                cantidad=renglon["cantidad"],
                requiere_revision=concepto_id is None,
                confianza_normalizacion=renglon["confianza"],
            )

        tarea_id = uuid.uuid4()
        await repo.crear_tarea(
            id=tarea_id,
            lista_id=lista_id,
            origen=origen,
            estado="completada",
            version_id=version_id,
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
            contacto_referencia=contacto_referencia,
            preferencias=preferencias,
            colegio_datos=colegio_datos,
            documento=documento,
            percepcion_cruda=percepcion_cruda,
            clave_idempotencia=clave_idempotencia,
        )

    return {
        "version_id": str(version_id),
        "tarea_id": str(tarea_id),
        "items": len(renglones),
        "revisada": False,
    }


@router.post(
    "/sugerencias",
    status_code=201,
    summary="Encolar la sugerencia de lista de un padre en el backlog del administrador",
)
async def crear_sugerencia(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Un padre cuyo (colegio, grado) no tiene lista verificada la sugiere.

    Nace como una `tarea_importacion` con origen='sugerencia_padre' y estado
    'pendiente': una sugerencia que espera a que un administrador la atienda,
    no una lista publicada. La traza al acudiente es SOLO su
    `contacto_referencia` (el usuario_id que Identidad emite); el correo y el
    telefono son PII que vive unicamente en Identidad y aqui ni se aceptan ni se
    guardan. La evidencia (PDF del padre) se decodifica de base64 y se guarda
    como bytes, igual que en `importar`; un base64 invalido es 422 sin repetir
    lo enviado, porque el documento puede traer nombres de menores.
    """
    try:
        colegio_id = uuid.UUID(str(cuerpo["colegio_id"]))
        grado = str(cuerpo["grado"])
        anio_lectivo = int(cuerpo["anio_lectivo"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ErrorDominio(
            "cuerpo_invalido", "Falta o es invalido un campo del cuerpo de la sugerencia.", estado=422
        ) from exc

    referencia_cruda = cuerpo.get("contacto_referencia")
    try:
        contacto_referencia = uuid.UUID(str(referencia_cruda)) if referencia_cruda is not None else None
    except (ValueError, TypeError) as exc:
        raise ErrorDominio(
            "contacto_invalido",
            "El contacto de referencia no es un identificador valido.",
            estado=422,
            campo="contacto_referencia",
        ) from exc

    evidencia = dict(cuerpo.get("evidencia") or {})
    documento_base64 = evidencia.get("documento_base64")
    documento: bytes | None = None
    if documento_base64 is not None:
        try:
            documento = base64.b64decode(str(documento_base64), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ErrorDominio(
                "documento_invalido",
                "La evidencia no trae un documento en base64 valido.",
                estado=422,
                campo="documento_base64",
            ) from exc

    tarea_id = uuid.uuid4()
    async with _motor().sesion() as db:
        await RepoAdmin(await db.connection()).crear_tarea(
            id=tarea_id,
            origen="sugerencia_padre",
            estado="pendiente",
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
            contacto_referencia=contacto_referencia,
            documento=documento,
        )

    return {"tarea_id": str(tarea_id), "estado": "pendiente"}


@router.get(
    "/sugerencias",
    summary="El backlog de sugerencias de padres que el administrador atiende",
)
async def listar_sugerencias() -> dict[str, Any]:
    """Las `tarea_importacion` con origen='sugerencia_padre', mas recientes primero.

    Devuelve SOLO campos seguros. La traza al acudiente es su `contacto_referencia`
    (el usuario_id que Identidad emite) y nada mas: el correo y el telefono son PII
    que vive unicamente en Identidad, asi que no se resuelven ni se unen aqui —de
    hecho no hay columna donde pudieran estar—. `tiene_documento` dice si hay PDF
    adjunto sin volcar los bytes en la lista.
    """
    async with _motor().engine.begin() as conexion:
        filas = await RepoAdmin(conexion).listar_sugerencias()
        datos = [
            {
                "tarea_id": str(f.id),
                "estado": f.estado,
                "colegio_id": None if f.colegio_id is None else str(f.colegio_id),
                "grado": f.grado,
                "anio_lectivo": None if f.anio_lectivo is None else int(f.anio_lectivo),
                "contacto_referencia": (
                    None if f.contacto_referencia is None else str(f.contacto_referencia)
                ),
                "tiene_documento": bool(f.tiene_documento),
            }
            for f in filas
        ]
    return {"sugerencias": datos}


@router.get(
    "/listas/{version_id}/documento",
    summary="El PDF original que dio lugar a esta version (region 1)",
)
async def documento_de_version(version_id: uuid.UUID) -> Response:
    async with _motor().engine.begin() as conexion:
        tarea = await RepoAdmin(conexion).tarea_con_evidencia(version_id)
        if tarea is None or tarea.documento is None:
            raise ErrorDominio(
                "sin_evidencia",
                "Esta version no tiene un documento de origen.",
                estado=404,
            )
        datos = bytes(tarea.documento)
        return Response(content=datos, media_type=_media_type_documento(datos))


@router.get(
    "/listas/{version_id}/percepcion",
    summary="Lo que la percepcion leyo por pagina y los renglones resultantes (region 2)",
)
async def percepcion_de_version(version_id: uuid.UUID) -> dict[str, Any]:
    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        tarea = await repo.tarea_con_evidencia(version_id)
        if tarea is None:
            raise ErrorDominio(
                "sin_evidencia",
                "Esta version no tiene percepcion de origen.",
                estado=404,
            )
        items = [
            {
                "texto_original": f.texto_original,
                "cantidad": int(f.cantidad),
                "confianza": None if f.confianza_normalizacion is None else float(f.confianza_normalizacion),
            }
            for f in await repo.items_percepcion(version_id)
        ]
    return {
        "version_id": str(version_id),
        "paginas": [_pagina_percepcion(p) for p in (tarea.percepcion_cruda or [])],
        "items": items,
    }


# ---------------------------------------------------------------------------
# Editar los renglones (solo sobre una version sin revisar)
# ---------------------------------------------------------------------------


async def _valores_de_renglon(repo: RepoAdmin, cuerpo: dict[str, Any], *, nuevo: bool) -> dict[str, Any]:
    """Traduce el cuerpo del cliente a columnas de `item_lista_oficial`.

    Valida contra el MISMO vocabulario que los CHECK del modelo antes de tocar
    la base: un tipo o un modo invalido es un 422 con el campo, no un error de
    integridad que aflora como 500. La regla `concepto_id NULL => requiere
    revision` tambien se dice aqui, porque el modelo la impone y el cliente
    tiene derecho a un mensaje y no a un choque de constraint.
    """
    valores: dict[str, Any] = {}
    if "texto_original" in cuerpo:
        valores["texto_original"] = str(cuerpo["texto_original"])
    elif nuevo:
        raise ErrorDominio(
            "texto_requerido",
            "Un renglon nuevo necesita texto_original.",
            estado=422,
            campo="texto_original",
        )
    if "cantidad" in cuerpo:
        cantidad = int(cuerpo["cantidad"])
        if cantidad <= 0:
            raise ErrorDominio(
                "cantidad_invalida",
                "La cantidad tiene que ser mayor que cero.",
                estado=422,
                campo="cantidad",
            )
        valores["cantidad"] = cantidad
    for campo, permitidos in (
        ("unidad", _UNIDADES),
        ("tipo_item", _TIPOS_ITEM),
        ("modo_adquisicion", _MODOS),
    ):
        if campo in cuerpo:
            valor = cuerpo[campo]
            # modo_adquisicion es NOT NULL: un null es tan invalido como un
            # valor fuera del vocabulario, y debe ser 422, no un 500.
            nulo_invalido = valor is None and campo == "modo_adquisicion"
            if nulo_invalido or (valor is not None and valor not in permitidos):
                raise ErrorDominio(
                    f"{campo}_invalido",
                    f"'{valor}' no es un {campo} valido.",
                    estado=422,
                    campo=campo,
                )
            valores[campo] = valor
    for campo in ("instruccion_colegio", "url_externa"):
        if campo in cuerpo:
            valores[campo] = cuerpo[campo]
    if "atributos" in cuerpo:
        atributos = cuerpo["atributos"] or {}
        # La misma guarda que los atributos de un producto (`dominio/catalogo`):
        # un mapa de valores simples. Una lista o un dict anidado no se compara
        # contra nada y, sin esto, `dict([...])` afloraba como un 500.
        if not isinstance(atributos, dict) or any(
            v is not None and not isinstance(v, (str, int, float)) for v in atributos.values()
        ):
            raise ErrorDominio(
                "atributos_invalido",
                "Los atributos son un mapa de valores simples (texto, numero o «*»).",
                estado=422,
                campo="atributos",
            )
        valores["atributos"] = {str(k): v for k, v in atributos.items()}
    if "concepto_codigo" in cuerpo:
        codigo = cuerpo["concepto_codigo"]
        valores["concepto_id"] = None if codigo is None else await _concepto_id(repo, codigo)
    if "requiere_revision" in cuerpo:
        valores["requiere_revision"] = bool(cuerpo["requiere_revision"])
    return valores


async def _exigir_atributos_curables(
    repo: RepoAdmin, valores: dict[str, Any], concepto_id: uuid.UUID | None, previos: dict[str, Any]
) -> None:
    """Que lo curado sea algo que la ruta rapida va a mirar.

    `_renglon_resuelto` ignora en silencio una clave que no es discriminante
    del concepto: curarla no cambiaria nada y el revisor creeria que si. Por
    eso se rechaza con el nombre de la clave. Lo que el renglon YA traia igual
    (curado para un concepto anterior, o de antes de esta guarda) se deja
    pasar: el editor devuelve el mapa entero y no debe fallar por lo que la
    persona no toco.
    """
    if "atributos" not in valores:
        return
    discriminantes = set(await repo.discriminantes_de_concepto(concepto_id))
    ajenos = sorted(
        k
        for k, v in valores["atributos"].items()
        if k not in discriminantes and not (k in previos and previos[k] == v)
    )
    if ajenos:
        permitidos = ", ".join(sorted(discriminantes)) or "ninguno: el concepto no filtra por atributos"
        raise ErrorDominio(
            "atributo_no_exigible",
            f"El concepto no filtra por {', '.join(ajenos)}. Se puede curar: {permitidos}.",
            estado=422,
            campo="atributos",
        )


@router.patch(
    "/listas/{version_id}/items/{item_id}",
    summary="Editar un renglon de una version sin revisar",
)
async def editar_item(version_id: uuid.UUID, item_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        _exigir_sin_revisar(cabeza)
        actual = await repo.item_por_id(item_id, version_id)
        if actual is None:
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)

        valores = await _valores_de_renglon(repo, cuerpo, nuevo=False)
        concepto_id = valores.get("concepto_id", actual.concepto_id)
        requiere = valores.get("requiere_revision", actual.requiere_revision)
        modo = valores.get("modo_adquisicion", actual.modo_adquisicion)
        instruccion = valores.get("instruccion_colegio", actual.instruccion_colegio)
        _cuidar_invariantes(concepto_id, requiere, modo, instruccion)
        await _exigir_atributos_curables(repo, valores, concepto_id, dict(actual.atributos or {}))
        if valores:
            await repo.actualizar_item(item_id, valores)
    return {"item_id": str(item_id), "actualizado": True}


@router.post(
    "/listas/{version_id}/items",
    status_code=201,
    summary="Agregar un renglon a una version sin revisar",
)
async def agregar_item(version_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        _exigir_sin_revisar(cabeza)

        valores = await _valores_de_renglon(repo, cuerpo, nuevo=True)
        concepto_id = valores.get("concepto_id")
        requiere = valores.get("requiere_revision", concepto_id is None)
        valores["requiere_revision"] = requiere
        _cuidar_invariantes(
            concepto_id,
            requiere,
            valores.get("modo_adquisicion"),
            valores.get("instruccion_colegio"),
        )
        await _exigir_atributos_curables(repo, valores, concepto_id, {})

        # El siguiente orden libre: el ultimo mas uno, para no chocar con el
        # indice unico (version_id, orden).
        orden = await repo.max_orden_item(version_id) + 1
        nuevo_id = uuid.uuid4()
        await repo.crear_item(id=nuevo_id, version_id=version_id, orden=orden, **valores)
    return {"item_id": str(nuevo_id), "orden": orden}


@router.delete(
    "/listas/{version_id}/items/{item_id}",
    status_code=204,
    summary="Quitar un renglon de una version sin revisar",
)
async def quitar_item(version_id: uuid.UUID, item_id: uuid.UUID) -> None:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        _exigir_sin_revisar(cabeza)
        if not await repo.borrar_item(item_id, version_id):
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)


@router.delete(
    "/listas/{version_id}",
    status_code=204,
    summary="Descartar una version sin revisar de la cola",
)
async def borrar_version(version_id: uuid.UUID) -> None:
    """Sacar de la cola una version que aun no se aprueba (una sugerencia que
    no va, un onboarding equivocado, una que se va a volver a subir). Solo SIN
    revisar: una version revisada es la lista oficial del colegio y no se borra
    —se corrige con una nueva—, misma puerta que editar. Los renglones y las
    propuestas caen por CASCADE, y la tarea de importacion se borra con ella:
    con SET NULL quedaria huerfana con el documento (el PDF de un acudiente)
    adentro. Si era la vigente, la vigencia vuelve a la ultima revisada.

    Un acudiente que esperaba esta version no se entera: su trabajo sigue en
    espera. La pantalla lo advierte antes de confirmar.
    """
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        _exigir_sin_revisar(cabeza)
        await repo.borrar_version(version_id)


# Los campos que el revisor puede completar del colegio nuevo antes de aprobar.
# Es una lista blanca: `nombre` y `dane` los fija la subida y no se reescriben
# aqui (cambiar el dane cambiaria el `colegio_id` derivado y desligaria la lista
# del colegio). Todos son datos de la INSTITUCION, no del menor: no son PII.
_CAMPOS_COLEGIO_EDITABLES = frozenset(
    {
        "nombre",
        "logo_url",
        "sitio_web",
        "direccion",
        "contacto_nombre",
        "contacto_email",
        "contacto_telefono",
    }
)


@router.patch(
    "/listas/{version_id}/colegio",
    summary="Completar los datos del colegio nuevo de una version sin revisar",
)
async def completar_colegio(version_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """El revisor completa el perfil del colegio que se dara de alta al aprobar.

    Para que el colegio se vaya COMPLETO (logo, direccion, contacto...) y no solo
    con nombre y grado. Se hace un merge sobre `colegio_datos` de la tarea: los
    campos que llegan reemplazan; los que no, se conservan. `dane` no se toca
    —cambia el `colegio_id` derivado y desligaria la lista del colegio—. Solo
    sobre una version SIN revisar (despues, se corrige con una version nueva) y
    solo si hay un colegio nuevo que completar (un aliado ya conocido es 409).
    """
    parche = {k: cuerpo[k] for k in cuerpo if k in _CAMPOS_COLEGIO_EDITABLES}
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        _exigir_sin_revisar(cabeza)

        tarea = await repo.tarea_colegio_datos(version_id)
        if tarea is None or tarea.colegio_datos is None:
            raise ErrorDominio(
                "sin_colegio_por_crear",
                "Esta lista es de un colegio ya aliado: no hay un colegio nuevo que completar.",
                estado=409,
            )

        datos = dict(tarea.colegio_datos)
        datos.update(parche)
        await repo.actualizar_colegio_datos(tarea.id, datos)
    return {"version_id": str(version_id), "colegio_datos": datos}


# ---------------------------------------------------------------------------
# Decidir propuestas
# ---------------------------------------------------------------------------


@router.post("/propuestas/{prop_id}/rechazar", summary="Rechazar una propuesta pendiente")
async def rechazar_propuesta(prop_id: uuid.UUID, cuerpo: dict[str, Any] | None = None) -> dict[str, Any]:
    """El rechazo corriente: descarta ESTA propuesta y deja el concepto abierto.

    El rechazo de concepto entero (`no_surtir`) y la aprobacion, que crean o
    tocan `producto_canonico` y salen del camino de la revision de la lista,
    siguen en `descubrir.resolver` porque dependen de Postgres y de la red; esta
    ruta cubre lo que la pantalla de revision necesita para poder cerrar: dejar
    cero propuestas pendientes.
    """
    from datetime import UTC, datetime

    motivo = (cuerpo or {}).get("motivo")
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        fila = await repo.propuesta_estado(prop_id)
        if fila is None:
            raise ErrorDominio(
                "propuesta_no_existe",
                "No hay ninguna propuesta con ese identificador.",
                estado=404,
            )
        if fila.estado != "pendiente":
            raise ErrorDominio("propuesta_ya_resuelta", f"Esa propuesta ya esta {fila.estado}.", estado=409)
        await repo.rechazar_propuesta(prop_id, motivo, datetime.now(UTC))
    return {"id": str(prop_id), "estado": "rechazada"}


# ---------------------------------------------------------------------------
# Cerrar (aprobar) y nueva version (corregir)
# ---------------------------------------------------------------------------


async def _aprobar(repo: RepoAdmin, version_id: uuid.UUID, cabeza: Any) -> None:
    """Marca revisada la version, le pasa la vigencia y emite sus eventos."""
    from datetime import UTC, datetime

    await repo.marcar_revisada(version_id, datetime.now(UTC))

    # Aprobar es lo que le pasa la vigencia a esta version: al editar, el
    # borrador nacio SIN vigencia para que el acudiente siguiera viendo la
    # anterior; ahora que se aprueba, se degrada la vigente actual y se
    # promueve esta, en ESTA misma transaccion, para respetar el indice
    # parcial de una sola vigente por lista. Es no-op en el onboarding de
    # estreno: la version aprobada ya era la unica vigente (se degrada y se
    # re-promueve la misma fila).
    await repo.desvigar_versiones(cabeza.lista_id)
    await repo.promover_vigente(version_id)

    # Toda version aprobada estrena sus kits canonicos: Inteligencia drena
    # `lista_aprobada`, arma Ahorrador y Premium sin preferencias (ADR 0030)
    # y los fija como la cache del grado, para que el proximo acudiente sin
    # tope de gasto los reciba sin volver a correr el optimizador. Va ANTES
    # que `lista_verificada` (la bandeja se drena por id) y por la misma
    # razon de grafo: Catalogo no llama a Inteligencia, le deja el evento.
    await repo.emitir_evento(
        tipo="lista_aprobada",
        agregado_tipo="version_lista_oficial",
        agregado_id=version_id,
        carga={
            "colegio_id": str(cabeza.colegio_id),
            "grado": cabeza.grado,
            "anio_lectivo": cabeza.anio_lectivo,
        },
    )

    # Si un padre estaba esperando esta version (subio su PDF y quedo ligado
    # por `contacto_referencia`), aprobarla dispara su kit: un
    # `lista_verificada` en la bandeja, EN LA MISMA transaccion que el
    # `revisada_en`, que el poller de Inteligencia drena para armar el
    # trabajo de ruta rapida con sus preferencias. Catalogo NO llama a
    # Inteligencia: esa arista cerraria un ciclo en el grafo de dependencias.
    # Sin padre esperando no se emite: el kit del grado ya sale del
    # `lista_aprobada` de arriba, sin pasar por la cola (ADR 0029).
    tarea = await repo.tarea_para_evento(version_id)
    contacto = tarea.contacto_referencia if tarea is not None else None
    if contacto is not None:
        await repo.emitir_evento(
            tipo="lista_verificada",
            agregado_tipo="version_lista_oficial",
            agregado_id=version_id,
            carga={
                # El padre, por identificador; NUNCA su correo/telefono.
                "contacto_referencia": str(contacto),
                "colegio_id": str(cabeza.colegio_id),
                "grado": cabeza.grado,
                "anio_lectivo": cabeza.anio_lectivo,
                # Lo que el padre pidio en el paso 3, para optimizar su kit.
                "preferencias": tarea.preferencias or {},
            },
        )

    # Si la lista se subio para un colegio que AUN NO existe en Tukit (trae
    # `colegio_datos`: lo eligio del directorio de Bogota o lo escribio),
    # aprobarla es lo que lo vuelve aliado. Catalogo NO llama a Identidad
    # —esa arista tampoco existe en el grafo—: emite `colegio_verificado` en
    # la MISMA transaccion, y un poller de Identidad crea el colegio con el
    # MISMO `colegio_id` que Catalogo ya derivo (de forma estable del DANE o
    # del nombre), de modo que la lista y el colegio quedan ligados sin FK
    # entre bases. El `nit` es el DANE; el resto son datos que el revisor
    # completo antes de aprobar. Un colegio aliado ya conocido no lo trae.
    if tarea is not None and tarea.colegio_datos:
        datos = dict(tarea.colegio_datos)
        await repo.emitir_evento(
            tipo="colegio_verificado",
            agregado_tipo="colegio",
            agregado_id=cabeza.colegio_id,
            carga={
                "colegio_id": str(cabeza.colegio_id),
                "grado": cabeza.grado,
                # El padre que esperaba este colegio, por identificador
                # opaco; NUNCA su correo/telefono, igual que en
                # `lista_verificada`. Va None en el onboarding de admin
                # (colegio dado de alta sin padre esperando): el guard de
                # este bloque es `colegio_datos`, no `contacto_referencia`.
                "contacto_referencia": None if contacto is None else str(contacto),
                "nombre": datos.get("nombre"),
                # El DANE es el `nit` del colegio en Identidad.
                "nit": datos.get("dane") or datos.get("nit"),
                "logo_url": datos.get("logo_url"),
                "sitio_web": datos.get("sitio_web"),
                "direccion": datos.get("direccion"),
                "contacto_nombre": datos.get("contacto_nombre"),
                "contacto_email": datos.get("contacto_email"),
                "contacto_telefono": datos.get("contacto_telefono"),
            },
        )


@router.post(
    "/listas/{version_id}/cerrar",
    summary="Dar por revisada una version: la habilita para el acudiente",
)
async def cerrar_version(version_id: uuid.UUID) -> dict[str, Any]:
    """La aprobacion. Se niega si queda una propuesta sin decidir.

    Es la misma regla de `descubrir.cerrar`: cerrar con propuestas pendientes
    dejaria el renglon sin producto y sin forma de reintentar, porque la puerta
    cerrada impide reabrir la busqueda. Marca `revisada_en` y desde ese momento
    la lista responde con el catalogo, sin consultar tiendas.
    """

    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await repo.version_y_lista(version_id)
        if cabeza is None:
            raise ErrorDominio(
                "version_no_existe",
                "No hay ninguna version con ese identificador.",
                estado=404,
            )
        if cabeza.revisada_en is not None:
            return {"version_id": str(version_id), "revisada": True, "ya_estaba": True}
        pendientes = await repo.contar_propuestas_pendientes(version_id)
        if pendientes:
            raise ErrorDominio(
                "propuestas_pendientes",
                f"Quedan {pendientes} propuestas sin decidir. Resuelvelas antes de cerrar.",
                estado=409,
            )
        await _aprobar(repo, version_id, cabeza)
    return {"version_id": str(version_id), "revisada": True}


async def _clonar_vigente(repo: RepoAdmin, lista: Any, vigente: Any) -> tuple[uuid.UUID, int]:
    """Copia la version vigente en una nueva SIN revisar y sin vigencia."""
    nuevo_numero = await repo.max_numero_version(lista.id) + 1
    nuevo_id = uuid.uuid4()
    await repo.crear_version(nuevo_id, lista.id, nuevo_numero, vigente=False)
    for r in await repo.items_para_clonar(vigente.id):
        await repo.crear_item(
            id=uuid.uuid4(),
            version_id=nuevo_id,
            orden=r.orden,
            texto_original=r.texto_original,
            concepto_id=r.concepto_id,
            cantidad=r.cantidad,
            unidad=r.unidad,
            tipo_item=r.tipo_item,
            modo_adquisicion=r.modo_adquisicion,
            instruccion_colegio=r.instruccion_colegio,
            url_externa=r.url_externa,
            atributos=dict(r.atributos or {}),
            requiere_revision=r.requiere_revision,
            avisos_descartados=list(r.avisos_descartados or ()),
        )

    # Copiar la evidencia (PDF + percepcion cruda) de la vigente al
    # borrador, para que el revisor de 4 paneles de onboarding pueda abrirlo
    # sin 404: `/documento` y `/percepcion` cuelgan de una `tarea_importacion`
    # ligada por `version_id`, que el clonado de VERSION/ITEM no arrastra. Se
    # anula `contacto_referencia` y `preferencias`: es una correccion del
    # administrador, no la subida de un padre —al re-aprobar NO debe re-armar
    # el kit de nadie (cerrar_version solo emite `lista_verificada` cuando
    # hay contacto_referencia). Una lista sembrada/CLI sin tarea no se copia:
    # queda sin evidencia, igual que hoy.
    origen_tarea = await repo.tarea_origen(vigente.id)
    if origen_tarea is not None:
        await repo.crear_tarea(
            id=uuid.uuid4(),
            lista_id=lista.id,
            origen=origen_tarea.origen,
            estado="completada",
            version_id=nuevo_id,
            colegio_id=origen_tarea.colegio_id,
            grado=origen_tarea.grado,
            anio_lectivo=origen_tarea.anio_lectivo,
            contacto_referencia=None,
            preferencias=None,
            colegio_datos=origen_tarea.colegio_datos,
            documento=origen_tarea.documento,
            percepcion_cruda=origen_tarea.percepcion_cruda,
        )
    return nuevo_id, nuevo_numero


@router.post(
    "/listas/{colegio_id}/{grado}/nueva-version",
    status_code=201,
    summary="Clonar la version vigente en una nueva SIN revisar, para corregir",
)
async def nueva_version(
    colegio_id: uuid.UUID,
    grado: str,
    anio_lectivo: Annotated[int, Query(ge=2020, le=2100)],
) -> dict[str, Any]:
    """Editar despues de aprobar sin borrar contra que compro quien ya compro.

    Clona la version VIGENTE en `max(numero)+1`, nace SIN revisar y SIN
    vigencia: la vigente publicada NO cambia hasta que el administrador cierre
    (aprueba) la correccion, y solo entonces `cerrar_version` le pasa la
    vigencia. Asi el acudiente sigue viendo la lista aprobada mientras se
    corrige, y la cola de administracion muestra el borrador por ser la de
    numero mayor. Se exige que la vigente ya este revisada: no se edita-clona
    algo nunca publicado.
    """
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        lista = await repo.lista_por_llave(colegio_id, grado, anio_lectivo)
        if lista is None:
            raise ErrorDominio(
                "lista_no_existe",
                "No hay ninguna lista para ese colegio, grado y ano.",
                estado=404,
            )

        vigente = await repo.version_vigente(lista.id)
        if vigente is None:
            raise ErrorDominio("version_no_existe", "La lista no tiene version vigente.", estado=404)
        if vigente.revisada_en is None:
            raise ErrorDominio(
                "lista_no_revisada",
                "Solo se puede editar una lista ya revisada. Esta version aun esta en revision: "
                "corrigela y aprubala en la cola en vez de crear otra.",
                estado=409,
            )

        # El borrador nace SIN vigencia: la vigente publicada no cambia (el
        # acudiente la sigue viendo) hasta que se apruebe la correccion. Se
        # numera con max(numero)+1, no vigente.numero+1, para que un segundo
        # Editar sobre la misma vigente no choque con el uq (lista_id, numero)
        # del borrador anterior.
        nuevo_id, nuevo_numero = await _clonar_vigente(repo, lista, vigente)
    return {"version_id": str(nuevo_id), "numero": nuevo_numero, "revisada": False}


# ---------------------------------------------------------------------------
# Avisos de una lista revisada
#
# Lo que la revision automatica no puede decidir sola y una persona si: un
# renglon que parece repetir a otro, uno que nombra varios valores de un
# atributo (y por eso no se exigio ninguno) y uno que pide algo que ningun
# producto cumple. Salen del MISMO calculo que la ruta rapida (`/resueltos`),
# asi que lo que se avisa es exactamente lo que le paso al kit.
# ---------------------------------------------------------------------------

_BUSCA_EN_CATALOGO = frozenset({"util", "libro_libre"})


def _avisos_de(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_orden = {i["orden"]: i for i in items}
    avisos: list[dict[str, Any]] = []
    for i in items:
        base = {
            "item_id": i["item_id"],
            "orden": i["orden"],
            "texto": i["texto_original"],
            "concepto_codigo": i["concepto_codigo"],
            "concepto_nombre": i["concepto_nombre"],
        }
        descartados = set(i.get("avisos_descartados") or ())
        repite = i.get("posible_repetido_de")
        if repite is not None and f"repetido:{repite}" not in descartados:
            otro = por_orden.get(repite)
            avisos.append(
                {
                    **base,
                    "tipo": "posible_repetido",
                    "clave": f"repetido:{repite}",
                    "repite_a": repite,
                    "texto_repetido": otro["texto_original"] if otro else None,
                }
            )
        for atributo in i.get("atributos_por_revisar") or ():
            if f"revisar:{atributo}" not in descartados:
                avisos.append(
                    {**base, "tipo": "revisar_atributo", "clave": f"revisar:{atributo}", "atributo": atributo}
                )
        tipo = i.get("tipo_item") or i.get("tipo_concepto") or "util"
        surtible = (
            i["concepto_codigo"] is not None
            and tipo in _BUSCA_EN_CATALOGO
            and i["modo_adquisicion"] in ("mercado_abierto", "libro_libre")
        )
        if surtible and not i["candidatos"] and "sin_producto" not in descartados:
            avisos.append(
                {**base, "tipo": "sin_producto", "clave": "sin_producto", "exige": i["atributos_impuestos"]}
            )
    return avisos


async def _version_revisada(repo: RepoAdmin, version_id: uuid.UUID) -> Any:
    cabeza = await repo.version_y_lista(version_id)
    if cabeza is None:
        raise ErrorDominio("version_no_existe", "No hay ninguna version con ese identificador.", estado=404)
    if cabeza.revisada_en is None:
        raise ErrorDominio(
            "lista_no_revisada",
            "Los avisos son de una lista ya revisada; esta aun esta en revision.",
            estado=409,
        )
    return cabeza


@router.get(
    "/listas/{version_id}/avisos", summary="Lo que una persona tiene que decidir de una lista revisada"
)
async def avisos_de_version(version_id: uuid.UUID) -> dict[str, Any]:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        await _version_revisada(repo, version_id)
        avisos = _avisos_de(await _renglones_resueltos(repo, version_id))
    return {"version_id": str(version_id), "avisos": avisos}


@router.post(
    "/listas/{version_id}/avisos/descartar",
    summary='El aviso no aplica ("son distintos"): no vuelve a salir',
)
async def descartar_aviso(version_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Se guarda en el renglon y no crea version: no cambia lo que se compra."""
    clave = str(cuerpo.get("clave") or "").strip()
    if not re.fullmatch(r"repetido:\d+|revisar:[a-z_]+|sin_producto", clave):
        raise ErrorDominio("aviso_invalido", "Ese aviso no existe.", estado=400)
    try:
        item_id = uuid.UUID(str(cuerpo.get("item_id")))
    except ValueError as error:
        raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404) from error
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        await _version_revisada(repo, version_id)
        if not await repo.descartar_aviso(item_id, version_id, clave):
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)
    return {"item_id": str(item_id), "descartado": clave}


@router.post(
    "/listas/{version_id}/items/{item_id}/no-comprar",
    status_code=201,
    summary="El renglon repite a otro: no se compra. Publica una version nueva",
)
async def no_comprar_repetido(
    version_id: uuid.UUID, item_id: uuid.UUID, cuerpo: dict[str, Any]
) -> dict[str, Any]:
    """ "Es el mismo": el renglon queda en la lista como "no se compra · ya va en
    la linea N" y la lista se vuelve a publicar.

    Es el mismo camino que «Editar» + «Aprobar» de la pagina del grado, en un
    paso: clona la vigente, cambia ese renglon y aprueba la copia. Aprobar le
    pasa la vigencia y emite `lista_aprobada`, asi que Inteligencia rearma los
    kits canonicos con la lista corregida. La version anterior queda para quien
    ya compro con ella.
    """
    repite_a = cuerpo.get("repite_a")
    if not isinstance(repite_a, int):
        raise ErrorDominio("repite_a_requerido", "Falta el renglon al que repite.", estado=400)
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        cabeza = await _version_revisada(repo, version_id)
        actual = await repo.item_por_id(item_id, version_id)
        if actual is None:
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)
        lista = await repo.lista_por_llave(cabeza.colegio_id, cabeza.grado, cabeza.anio_lectivo)
        vigente = await repo.version_vigente(lista.id)
        if vigente is None or vigente.id != version_id:
            raise ErrorDominio(
                "version_no_vigente",
                "Esa ya no es la lista vigente del grado; recarga la pagina.",
                estado=409,
            )

        nuevo_id, nuevo_numero = await _clonar_vigente(repo, lista, vigente)
        copia = await repo.item_por_orden(nuevo_id, int(actual.orden))
        await repo.actualizar_item(
            copia.id,
            {
                "tipo_item": "no_comprar",
                "instruccion_colegio": f"Es el mismo de la linea {repite_a}: no se compra dos veces.",
            },
        )
        nueva = await repo.version_y_lista(nuevo_id)
        await _aprobar(repo, nuevo_id, nueva)
    return {"version_id": str(nuevo_id), "numero": nuevo_numero}


# ---------------------------------------------------------------------------
# Curaduria proactiva del catalogo (la mitad de `admin` que la SPA necesita)
#
# La cola de propuestas en JSON, la busqueda en tienda, el alta de util/libro y
# la aprobacion, todo bajo `/v1/admin/catalogo/*`. Reusa `_encolar`/`resolver`/
# `tiendas.buscar` de `descubrir`/`admin` sin reimplementar dominio: encolar y
# aprobar son DOS pasos separados aqui (a diferencia del CLI), para que la
# propuesta caiga en la cola visible y una persona decida el nivel al aprobar.
# ---------------------------------------------------------------------------


@router.get(
    "/catalogo/propuestas",
    summary="La cola de propuestas pendientes de curaduria, en JSON",
)
async def cola_propuestas(
    concepto: Annotated[str | None, Query(description="Filtrar por codigo de concepto")] = None,
) -> dict[str, Any]:
    """La misma cola que `descubrir.listar_pendientes`, pero devuelta como JSON.

    Es el gemelo HTTP de la vista de `admin._leer_cola`: `estado=='pendiente'`,
    ordenada por `propuesta_en`, con lo que la tarjeta necesita para decidir sin
    salir a la tienda. El precio va en pesos (centavos // 100). El concepto sale
    resuelto (`{codigo, nombre}`) o, si la propuesta trae un concepto sugerido
    nuevo, como `{sugerido}`. Filtro opcional por codigo de concepto.
    """
    async with _motor().engine.begin() as conexion:
        filas = await RepoAdmin(conexion).cola_propuestas(concepto)
        propuestas = [
            {
                "id": str(p.id),
                "id_corto": str(p.id)[:8],
                "texto_origen": p.texto_origen,
                "nombre": p.nombre,
                "marca": p.marca,
                "imagen_url": p.imagen_url,
                "precio": None if p.precio_centavos is None else int(p.precio_centavos) // 100,
                "nivel_sugerido": p.nivel_sugerido,
                "puntaje": float(p.puntaje or 0),
                "concepto": (
                    {"codigo": p.concepto_codigo, "nombre": p.concepto_nombre}
                    if p.concepto_codigo
                    else {"sugerido": p.concepto_sugerido}
                ),
                "origen": p.origen,
                # Lo que quien propuso verifico contra la ficha de la tienda, y
                # los atributos con que nace el producto si se aprueba tal cual
                # (eso mas lo que dice el nombre): el editor arranca con estos.
                "atributos_verificados": atributos_verificados(dict(p.especificaciones or {})),
                "atributos_al_aprobar": atributos_al_aprobar(
                    p.nombre,
                    dict(p.especificaciones or {}),
                    tuple(p.atributos_discriminantes or ()) + tuple(p.atributos_descriptivos or ()),
                ),
            }
            for p in filas
        ]
    return {"total": len(propuestas), "propuestas": propuestas}


@router.get(
    "/catalogo/tiendas/{slug}/buscar",
    summary="Candidatos en vivo de una tienda para el alta de util (no escribe)",
)
async def buscar_en_tienda(
    slug: str,
    consulta: Annotated[str, Query(description="Que buscar en la tienda")],
    cuantos: Annotated[int, Query(ge=1, le=48)] = 24,
) -> dict[str, Any]:
    """Envuelve `tiendas.buscar` para el buscador del alta de util.

    Solo lectura externa: NO escribe. Solo las tres tiendas con busqueda en vivo
    (VTEX/Shopify); otro slug es un 422 con causa, no un 500. La busqueda es sync
    y con cache en disco, asi que se corre en un hilo (`run_in_threadpool`) para
    no bloquear el loop. El precio va en pesos, como lo devuelve la tienda.
    """
    from starlette.concurrency import run_in_threadpool

    from .. import tiendas

    if slug not in _SLUGS_TIENDA:
        raise ErrorDominio(
            "tienda_desconocida",
            f"No conozco la tienda '{slug}'. Solo {', '.join(sorted(_SLUGS_TIENDA))}.",
            estado=422,
            campo="slug",
        )
    ofertas = await run_in_threadpool(tiendas.buscar, slug, consulta, cuantos)
    return {
        "candidatos": [
            {
                "slug": slug,
                "sku": o.sku,
                "nombre": o.nombre,
                "precio": o.precio_cop,
                "marca": o.marca,
                "ean": o.ean,
                "url": o.url,
                "imagen_url": o.imagen_url,
                "disponible": o.disponible,
                "especificaciones": o.especificaciones or {},
            }
            for o in ofertas
        ]
    }


@router.post(
    "/catalogo/conceptos",
    status_code=201,
    summary="Crear un concepto nuevo (para encolar sus productos despues)",
)
async def crear_concepto(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Da de alta un concepto que el corpus no tenia, para poder encolarle sus
    tres niveles enseguida. Es el otro brazo del bucle de curacion: cuando el
    revisor ve un renglon que no empareja con nada ("Plan lector RAZ-PLUS") crea
    el concepto y luego le agrega productos, de modo que la BD crezca revisando.

    El `codigo` se autogenera (el siguiente `C0NN` libre) para no cargarle al
    revisor el esquema de codigos. `nombre_canonico` y `categoria` son
    obligatorios; los sinonimos ayudan al matcher a reconocerlo en la proxima
    lista y llegan como lista o como texto separado por `|`. `tipo_item` cae a
    `util` (lo comprable, el caso comun). El id se deriva del codigo con el
    contrato compartido, igual que el cargador, para que sea idempotente.
    """
    nombre = str(cuerpo.get("nombre_canonico") or cuerpo.get("nombre") or "").strip()
    categoria = str(cuerpo.get("categoria") or "").strip()
    if not nombre:
        raise ErrorDominio(
            "nombre_invalido", "El concepto necesita un nombre canonico.", estado=422, campo="nombre_canonico"
        )
    if not categoria:
        raise ErrorDominio(
            "categoria_invalida", "El concepto necesita una categoria.", estado=422, campo="categoria"
        )
    tipo_item = str(cuerpo.get("tipo_item") or TipoItem.UTIL.value)
    if tipo_item not in {t.value for t in TipoItem}:
        raise ErrorDominio(
            "tipo_item_invalido", f"Tipo de item desconocido: {tipo_item}.", estado=422, campo="tipo_item"
        )
    crudo = cuerpo.get("sinonimos") or []
    sinonimos = (
        [s.strip() for s in crudo.split("|") if s.strip()]
        if isinstance(crudo, str)
        else [str(s).strip() for s in crudo if str(s).strip()]
    )
    # Los dos papeles del atributo (ver `demanda_atributos`): el discriminante
    # FILTRA (un cuaderno cuadriculado no pasa por uno rayado) y el descriptivo
    # solo informa. Se normalizan a la forma del corpus (minusculas, `_` por
    # espacio) y no pueden repetirse entre listas: la base lo prohibe.
    discriminantes = _nombres_de_atributo(cuerpo.get("atributos_discriminantes"))
    descriptivos = [
        a for a in _nombres_de_atributo(cuerpo.get("atributos_descriptivos")) if a not in discriminantes
    ]

    from ..cargador import _uuid_estable

    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        # El nombre canonico ya existente es el choque real: dos "cuaderno" con
        # codigos distintos partirian el vocabulario del matcher. El codigo se
        # autogenera, asi que no puede chocar.
        ya = await repo.concepto_codigo_por_nombre(nombre.lower())
        if ya is not None:
            raise ErrorDominio(
                "concepto_ya_existe",
                f"Ya existe un concepto '{nombre}' ({ya}). Agregale productos en vez de duplicarlo.",
                estado=409,
                campo="nombre_canonico",
            )
        # El siguiente C0NN libre: se lee el maximo actual y se suma uno. El
        # formato lo fija el corpus (C001..C0NN); mantenerlo deja que CLI y cola
        # compartan el mismo espacio de codigos.
        codigos = await repo.codigos_concepto()
        maximo = max((int(c[1:]) for c in codigos if c[1:].isdigit()), default=0)
        codigo = f"C{maximo + 1:03d}"

        await repo.crear_concepto(
            id=_uuid_estable("concepto", codigo),
            codigo=codigo,
            nombre_canonico=nombre,
            sinonimos=sinonimos,
            categoria=categoria,
            tipo_item=tipo_item,
            admite_personaje=bool(cuerpo.get("admite_personaje", False)),
            atributos_discriminantes=discriminantes,
            atributos_descriptivos=descriptivos,
        )
    return {
        "codigo": codigo,
        "nombre_canonico": nombre,
        "categoria": categoria,
        "tipo_item": tipo_item,
        "atributos_discriminantes": discriminantes,
        "atributos_descriptivos": descriptivos,
    }


def _nombres_de_atributo(crudo: Any) -> list[str]:
    """Lista o texto separado por `|`/`,` a nombres de atributo sin repetir."""
    if not crudo:
        return []
    partes = re.split(r"[|,]", crudo) if isinstance(crudo, str) else [str(p) for p in crudo]
    vistos: list[str] = []
    for parte in partes:
        nombre = re.sub(r"\s+", "_", parte.strip().lower())
        if nombre and nombre not in vistos:
            vistos.append(nombre)
    return vistos


@router.post(
    "/catalogo/propuestas/util",
    status_code=201,
    summary="Encolar un util elegido de una tienda (encola, NO aprueba)",
)
async def encolar_util(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Encola el candidato elegido; la aprobacion es un paso aparte.

    Re-busca por `(slug, sku)` para no confiar en que el navegador arme la
    Oferta: el precio y la ficha salen de la tienda, no del cliente. La busqueda
    es la MISMA que alimento la pantalla (`buscar_en_tienda`: una tienda, sin
    filtrar), y no `admin.buscar_candidatos`. Aquella aplica el quinto filtro
    (`_coincide`: TODAS las palabras de la consulta en el nombre), que existe
    para cuando la maquina elige sola; aqui ya eligio una persona mirando el
    producto. Con el filtro, "Pluma para caligrafia" rechazaba cualquier
    "Pilot Pluma Pen Caligrafia" porque el nombre no dice "para", y el
    revisor veia "ya no esta disponible" de un producto disponible.

    Si el candidato ya no aparece, o aparece agotado o sin precio, es un 422
    con causa, no un 500. El concepto se resuelve por codigo
    (`concepto_no_existe` si no existe) y el dict lo arma
    `construir_propuesta_util`, que HTTP y CLI comparten.
    """
    from starlette.concurrency import run_in_threadpool

    from .. import tiendas
    from ..descubrir import _encolar
    from ..dominio.propuesta import construir_propuesta_util

    consulta = str(cuerpo.get("consulta") or "").strip()
    slug = str(cuerpo.get("slug") or "")
    sku = str(cuerpo.get("sku") or "")
    nivel = str(cuerpo.get("nivel") or "confiable")
    codigo = str(cuerpo.get("concepto") or "")

    # El tope de `buscar_en_tienda`: el candidato pudo salir en cualquier
    # posicion de lo que la pantalla mostro.
    ofertas = await run_in_threadpool(tiendas.buscar, slug, consulta, 48)
    elegida = next((o for o in ofertas if o.sku == sku), None)
    if elegida is None:
        raise ErrorDominio(
            "candidato_no_disponible",
            "Ese candidato ya no aparece en la tienda; busca de nuevo.",
            estado=422,
            campo="sku",
        )
    if not elegida.disponible or elegida.precio_cop <= 0:
        raise ErrorDominio(
            "candidato_no_disponible",
            "La tienda tiene ese producto agotado o sin precio; elige otro.",
            estado=422,
            campo="sku",
        )

    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        concepto_id = await _concepto_id(repo, codigo)
        tienda_id = await repo.tienda_id_por_slug(slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = await repo.nombre_concepto(concepto_id)

    propuesta = construir_propuesta_util(concepto_id, nombre_concepto, slug, tienda_id, elegida, nivel)
    await _encolar([propuesta])
    return {"id": str(propuesta["id"]), "id_corto": str(propuesta["id"])[:8], "estado": "pendiente"}


@router.post(
    "/catalogo/propuestas/util-manual",
    status_code=201,
    summary="Encolar un util escrito a mano (sin busqueda en tienda; encola, NO aprueba)",
)
async def encolar_util_manual(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Encola un util que la persona escribe a mano, sin busqueda en vivo.

    Gemelo de `encolar_util` para lo que no aparece en la busqueda de la tienda
    (VTEX/Shopify no lo indexa, o es una tienda sin busqueda en vivo): la Oferta
    se arma del cuerpo en vez de re-buscarse por `(slug, sku)`. El precio es un
    entero > 0 en PESOS (`precio_invalido`) y el nombre no puede ir vacio
    (`nombre_invalido`); la tienda tiene que existir en la BD (`tienda_desconocida`,
    cualquiera de las registradas, no solo las de busqueda en vivo). El dict lo
    arma el mismo `construir_propuesta_util` que comparten HTTP y CLI, asi
    que el alta manual y la de busqueda nacen identicas al aprobarse.
    """
    from .. import tiendas
    from ..descubrir import _encolar
    from ..dominio.propuesta import _uuid_estable, construir_propuesta_util

    codigo = str(cuerpo.get("concepto") or "")
    nombre = str(cuerpo.get("nombre") or "").strip()
    if not nombre:
        raise ErrorDominio("nombre_invalido", "El util necesita un nombre.", estado=422, campo="nombre")
    try:
        precio = int(cuerpo.get("precio") or 0)
    except (TypeError, ValueError):
        precio = 0
    if precio <= 0:
        raise ErrorDominio(
            "precio_invalido",
            "El precio debe ser un entero mayor que cero en pesos.",
            estado=422,
            campo="precio",
        )
    slug = str(cuerpo.get("slug") or "")
    # Sin SKU de tienda, se deriva uno estable de (slug, nombre) para que
    # reencolar el mismo util a mano no lo duplique (la llave natural es
    # tienda+referencia, y `construir_propuesta_util` usa el sku como referencia).
    sku = str(cuerpo.get("sku") or "").strip() or _uuid_estable("util-manual", slug, nombre).hex[:12]
    url = str(cuerpo.get("url") or "").strip()
    marca = str(cuerpo.get("marca") or "").strip() or None
    nivel = str(cuerpo.get("nivel") or "confiable")

    oferta = tiendas.Oferta(
        tienda=slug,
        nombre=nombre,
        precio_cop=precio,
        disponible=True,
        imagen_url=None,
        url=url,
        sku=sku,
        ean=None,
        marca=marca,
        especificaciones={},
    )

    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        concepto_id = await _concepto_id(repo, codigo)
        tienda_id = await repo.tienda_id_por_slug(slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = await repo.nombre_concepto(concepto_id)

    propuesta = construir_propuesta_util(concepto_id, nombre_concepto, slug, tienda_id, oferta, nivel)
    await _encolar([propuesta])
    return {"id": str(propuesta["id"]), "id_corto": str(propuesta["id"])[:8], "estado": "pendiente"}


@router.post(
    "/catalogo/propuestas/libro",
    status_code=201,
    summary="Encolar un libro por ISBN (encola, NO aprueba)",
)
async def encolar_libro(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Encola un libro dado de alta a mano; la aprobacion es un paso aparte.

    Un libro no se busca (lo identifica el ISBN de una edicion, no un titulo):
    la persona escribe ISBN, titulo y precio. El ISBN se valida con el digito de
    control (`isbn_invalido` si no pasa) y el precio tiene que ser un entero > 0
    en pesos (`precio_invalido`). El dict lo arma `construir_propuesta_libro`.
    """
    from ..cargador import isbn13_valido, normalizar_isbn
    from ..descubrir import _encolar
    from ..dominio.propuesta import construir_propuesta_libro

    codigo = str(cuerpo.get("concepto") or "")
    isbn = normalizar_isbn(cuerpo.get("isbn")) or ""
    if not isbn13_valido(isbn):
        raise ErrorDominio(
            "isbn_invalido",
            "El ISBN no pasa el digito de control.",
            estado=422,
            campo="isbn",
        )
    titulo = str(cuerpo.get("titulo") or "").strip()
    try:
        precio = int(cuerpo.get("precio") or 0)
    except (TypeError, ValueError):
        precio = 0
    if precio <= 0:
        raise ErrorDominio(
            "precio_invalido",
            "El precio debe ser un entero mayor que cero en pesos.",
            estado=422,
            campo="precio",
        )
    slug = str(cuerpo.get("slug") or "panamericana")
    nivel = str(cuerpo.get("nivel") or "confiable")

    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        concepto_id = await _concepto_id(repo, codigo)
        tienda_id = await repo.tienda_id_por_slug(slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = await repo.nombre_concepto(concepto_id)

    propuesta = construir_propuesta_libro(
        concepto_id, nombre_concepto, slug, tienda_id, isbn, titulo, precio, nivel
    )
    await _encolar([propuesta])
    return {"id": str(propuesta["id"]), "id_corto": str(propuesta["id"])[:8], "estado": "pendiente"}


@router.post(
    "/catalogo/propuestas/{prop_id}/aprobar",
    summary="Aprobar una propuesta de la cola: nace el producto, su oferta y su precio",
)
async def aprobar_propuesta(prop_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """La aprobacion. Llama a `resolver` --el MISMO camino que aprueba una lista.

    No reimplementa el alta: `descubrir.resolver` es quien materializa el
    producto canonico, su oferta en la tienda y su primer precio, todo en una
    transaccion. Devuelve 0 en exito; cualquier otro codigo (la propuesta ya se
    resolvio, o le falta concepto) se traduce a un 409 con causa. La persona
    elige el nivel al aprobar, que puede diferir del sugerido.
    """
    from .. import descubrir

    nivel = str(cuerpo.get("nivel") or "confiable")

    # Correcciones a mano que la cola manda ANTES de aprobar: solo se reenvian
    # las claves presentes, para que resolver conserve el valor automatico de
    # las ausentes (aprobar sin correcciones sigue siendo identico a antes).
    overrides: dict[str, Any] = {}
    if isinstance(cuerpo.get("nombre"), str) and cuerpo["nombre"].strip():
        overrides["nombre"] = cuerpo["nombre"]
    for campo in ("marca", "imagen_url", "personaje"):
        if campo in cuerpo:
            valor = cuerpo[campo]
            # "" desde el formulario significa "sin dato": se guarda NULL.
            overrides[campo] = (valor.strip() or None) if isinstance(valor, str) else valor
    if isinstance(cuerpo.get("atributos"), dict):
        overrides["atributos"] = cuerpo["atributos"]

    codigo = await descubrir.resolver(
        str(prop_id)[:8], aprobar=True, nivel=nivel, motivo=None, overrides=overrides or None
    )
    if codigo != 0:
        raise ErrorDominio(
            "no_se_pudo_aprobar",
            "No se pudo aprobar. Puede que ya este resuelta o le falte concepto.",
            estado=409,
        )
    return {"id": str(prop_id), "estado": "aprobada"}
