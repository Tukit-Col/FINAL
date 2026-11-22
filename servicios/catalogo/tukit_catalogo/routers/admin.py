"""Superficie de escritura de la revision de listas, sobre HTTP.

Decisiones:
- Vive aparte de `api.py`, que es solo de lectura: la escritura del catalogo pasa por la cola de
  propuestas y por la mano de una persona, y separarla la deja auditable en un solo sitio.
- Una version ya revisada no se edita ni se reabre; la decision es la misma funcion que usa
  `descubrir` (`_exigir_sin_revisar`), no una copia.
- Escribe por el motor que el servicio ya tiene abierto (`app.state.motor`); el SQL vive en
  `repositorios/admin.RepoAdmin` y las reglas puras en `dominio/listas`.
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

from ..clasificacion import clasificar
from ..descubrir import atributos_al_aprobar, atributos_verificados
from ..dominio.listas import (
    _cuidar_invariantes,
    _exigir_sin_revisar,
    _item_publico,
    _pagina_percepcion,
)
from ..modelos.base import ModoAdquisicion, TipoItem, UnidadBase
from ..repositorios.admin import RepoAdmin

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_SLUGS_TIENDA = {"exito", "panamericana", "grancentral"}

UMBRAL_CONCEPTO = 0.5

_TIPOS_ITEM = {t.value for t in TipoItem}
_MODOS = {m.value for m in ModoAdquisicion}
_UNIDADES = {u.value for u in UnidadBase}


def _media_type_documento(datos: bytes) -> str:
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


_PREFIJO_GRUPO = re.compile(r"^[^:]{2,40}:\s*")
_CANTIDAD_INICIAL = re.compile(r"^(?:\d+|un|una|unos|unas|dos|tres|cuatro|cinco|seis|diez|doce)\b\s*", re.I)
_LARGO_SINONIMO = (4, 80)
_MAX_PALABRAS_SINONIMO = 6
_MARCA_DE_TITULO = re.compile(
    r"\beditorial\b|\bediciones\b|\bs\.a\.s\b|\bed\.|\bautor|\bedici[oó]n\b"
    r"|\. [a-záéíóúñ]+ [a-záéíóúñ]+\."
)


def sinonimo_de_renglon(texto: str) -> str | None:
    t = " ".join((texto or "").split())
    t = _PREFIJO_GRUPO.sub("", t)
    for _ in range(2):
        t = _CANTIDAD_INICIAL.sub("", t).strip()
    t = t.strip(" .,;:-").lower()
    if not (_LARGO_SINONIMO[0] <= len(t) <= _LARGO_SINONIMO[1]):
        return None
    if len(t.split()) > _MAX_PALABRAS_SINONIMO or _MARCA_DE_TITULO.search(t):
        return None
    return t


def _json(valor: Any) -> Any:
    if valor is None or isinstance(valor, (str, int, float, bool, list, dict)):
        return valor
    return str(valor)


async def _concepto_id(repo: RepoAdmin, codigo: str) -> uuid.UUID:
    cid = await repo.concepto_id_por_codigo(codigo)
    if cid is None:
        raise ErrorDominio(
            "concepto_no_existe", f"No existe el concepto {codigo}.", estado=422, campo="concepto_codigo"
        )
    return cid


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
                "procedencia": f.procedencia,
                "tiene_contacto": f.contacto_referencia is not None,
                "retirada_por_acudiente": bool(f.retirada_por_acudiente),
                "colegio_nombre": ((f.colegio_datos or {}).get("nombre") if f.colegio_datos else None),
            }
            for f in filas
        ]
    return {"total": len(datos), "listas": datos}


def _lo_que_se_exige(fila: Any, reglas: dict[str, tuple[tuple[str, ...], bool, str]]) -> dict[str, Any]:
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

        colegio_datos = await repo.colegio_datos_de(version_id)

    return {
        "version_id": str(cabeza.id),
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


_ORDEN_NIVEL = {"economico": 0, "confiable": 1, "premium": 2}

_SIN_REGLAS: tuple[tuple[str, ...], bool, str] = ((), False, "util")

_POR_MATERIA = frozenset({"C001"})


def _palabras(texto: str) -> set[str]:
    from ..extraccion import _normalizar

    return set(re.findall(r"[a-z0-9]+", _normalizar(texto)))


def _color_del_texto(texto: str) -> str | None:
    from ..extraccion import COLORES

    palabras = _palabras(texto)
    hallados = [
        canon for nombre, canon in COLORES if " " not in nombre and nombre in palabras and canon != "surtido"
    ]
    return hallados[-1] if hallados else None


def _posibles_repetidos(
    filas: list[Any], reglas: dict[str, tuple[tuple[str, ...], bool, str]]
) -> dict[int, int]:
    from ..extraccion import extraer_atributos

    vistos: dict[tuple[str, tuple[tuple[str, str], ...]], list[tuple[int, set[str]]]] = {}
    salida: dict[int, int] = {}
    for f in filas:
        codigo = f.concepto_codigo
        if codigo is None or codigo in _POR_MATERIA or reglas.get(codigo, _SIN_REGLAS)[1]:
            continue
        if (f.tipo_item or "util") in ("no_comprar", "uniforme", "licencia_digital", "diferido", "otro"):
            continue
        exige = extraer_atributos(f.texto_original, reglas.get(codigo, _SIN_REGLAS)[0])
        color = _color_del_texto(f.texto_original)
        if color and "color" not in exige:
            exige = {**exige, "color": color}
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


_PIDE_UN_JUEGO = re.compile(r"\b(?:cajas?|estuches?|paquetes?|set|kit|juegos?)\b")
_DE_LA_PIEZA = ("grosor", "forma")
NO_EXIGIR = "*"


def _lo_que_dice_el_texto(
    texto: str, discriminantes: tuple[str, ...], cantidad: int = 1
) -> tuple[dict[str, Any], list[str], bool]:
    from ..consulta import _NO_SE_EXIGEN
    from ..extraccion import _normalizar, atributos_ambiguos, extraer_atributos

    impuestos = {
        k: v for k, v in extraer_atributos(texto, discriminantes).items() if (k, v) not in _NO_SE_EXIGEN
    }
    por_revisar = [a for a in atributos_ambiguos(texto, discriminantes) if a not in impuestos]
    juego_inferido = False
    if "unidades" in discriminantes:
        plano = _normalizar(texto)
        primera = plano.split()[0] if plano.split() else ""
        if impuestos.get("unidades"):
            if por_revisar:
                for atributo in _DE_LA_PIEZA:
                    if impuestos.pop(atributo, None) is not None:
                        por_revisar.append(atributo)
        elif _PIDE_UN_JUEGO.search(plano) or (cantidad == 1 and primera.endswith("s")):
            impuestos["unidades"] = 2
            juego_inferido = True
    return impuestos, por_revisar, juego_inferido


def _con_lo_curado(
    leidos: dict[str, Any], curados: dict[str, Any], discriminantes: tuple[str, ...]
) -> dict[str, Any]:
    impuestos = dict(leidos)
    for k, v in curados.items():
        if k not in discriminantes or v in (None, ""):
            continue
        if v == NO_EXIGIR:
            impuestos.pop(k, None)
        else:
            impuestos[k] = v
    return impuestos


_POR_OMISION: dict[str, dict[str, str]] = {"C002": {"color": "negro"}}

_BLANDOS: dict[str, tuple[str, ...]] = {"C001": ("tamano",)}


def _lo_blando(texto: str, curados: dict[str, Any], concepto: str | None) -> dict[str, Any]:
    from ..extraccion import extraer_atributos

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
    texto = str(valor).lower()
    if atributo == "acabado":
        return True
    if atributo == "rayado":
        return any(c.isdigit() for c in texto) or texto.startswith("cuadricula ")
    return (atributo, texto) in {("punta", "micropunta"), ("tipo", "dibujo")}


def _sin_variantes_no_pedidas(
    productos: list[dict[str, Any]], impuestos: dict[str, Any], discriminantes: tuple[str, ...]
) -> list[dict[str, Any]]:
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
    from ..consulta import _cumple, del_mismo_titulo, pide_titulo

    if pide_titulo(discriminantes):
        productos = del_mismo_titulo(texto, productos)
    leidos, por_revisar, juego_inferido = _lo_que_dice_el_texto(texto, discriminantes, cantidad)
    impuestos = _con_lo_curado(leidos, curados, discriminantes)

    que_cumplen = [p for p in productos if _cumple(p, impuestos)]
    if not que_cumplen and juego_inferido and impuestos.get("unidades") == 2:
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

    Con `clave_idempotencia` el POST se puede reintentar: si ya entro
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

    origen = str(cuerpo.get("origen") or "onboarding")
    if origen not in ("onboarding", "sugerencia_padre"):
        raise ErrorDominio(
            "origen_invalido",
            "El origen de la importacion tiene que ser 'onboarding' o 'sugerencia_padre'.",
            estado=422,
            campo="origen",
        )

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

    preferencias_crudas = cuerpo.get("preferencias")
    if preferencias_crudas is not None and not isinstance(preferencias_crudas, dict):
        raise ErrorDominio(
            "preferencias_invalidas",
            "Las preferencias tienen que ser un objeto.",
            estado=422,
            campo="preferencias",
        )
    preferencias = preferencias_crudas or None

    referencias_crudas = cuerpo.get("referencias")
    if referencias_crudas is not None and not (
        isinstance(referencias_crudas, list)
        and all(isinstance(r, str) and 0 < len(r) <= 64 for r in referencias_crudas)
        and len(referencias_crudas) <= 10
    ):
        raise ErrorDominio(
            "referencias_invalidas",
            "Las referencias de los hijos tienen que ser una lista de textos.",
            estado=422,
            campo="referencias",
        )
    referencias = list(referencias_crudas) if referencias_crudas else None

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
            referencias=referencias,
            colegio_datos=colegio_datos,
            documento=documento,
            percepcion_cruda=percepcion_cruda,
            clave_idempotencia=clave_idempotencia,
        )
    except IntegrityError:
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
    referencias: list[str] | None = None,
) -> dict[str, Any]:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())

        lista = await repo.lista_por_llave(colegio_id, grado, anio_lectivo)
        if lista is None:
            lista_id = uuid.uuid4()
            await repo.crear_lista(lista_id, colegio_id, grado, anio_lectivo)
        else:
            lista_id = lista.id

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
            referencias=referencias,
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


async def _valores_de_renglon(repo: RepoAdmin, cuerpo: dict[str, Any], *, nuevo: bool) -> dict[str, Any]:
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
            await _registrar_cambios(repo, version_id, actual, valores)
    return {"item_id": str(item_id), "actualizado": True}


_CAMPO_DE_COLUMNA = {
    "concepto_id": "concepto",
    "cantidad": "cantidad",
    "texto_original": "texto",
    "modo_adquisicion": "modo",
    "tipo_item": "tipo",
    "atributos": "atributos",
    "instruccion_colegio": "instruccion",
    "requiere_revision": "revision",
    "unidad": "unidad",
    "url_externa": "url",
}


async def _registrar_cambios(
    repo: RepoAdmin, version_id: uuid.UUID, actual: Any, valores: dict[str, Any]
) -> None:
    for columna, despues in valores.items():
        antes = getattr(actual, columna, None)
        if antes == despues:
            continue
        aprendido = None
        if columna == "concepto_id":
            antes = await repo.codigo_de_concepto(actual.concepto_id)
            codigo = await repo.codigo_de_concepto(despues)
            sinonimo = sinonimo_de_renglon(actual.texto_original)
            if (
                despues is not None
                and sinonimo
                and await repo.aprender_sinonimo(sinonimo, despues, actual.concepto_id)
            ):
                aprendido = {"sinonimo": sinonimo, "concepto": codigo}
            despues = codigo
        await repo.registrar_correccion(
            version_id=version_id,
            item_id=actual.id,
            campo=_CAMPO_DE_COLUMNA.get(columna, columna)[:24],
            valor_antes=_json(antes),
            valor_despues=_json(despues),
            texto_original=actual.texto_original,
            aprendido=aprendido,
        )


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

        orden = await repo.max_orden_item(version_id) + 1
        nuevo_id = uuid.uuid4()
        await repo.crear_item(id=nuevo_id, version_id=version_id, orden=orden, **valores)
        await repo.registrar_correccion(
            version_id=version_id,
            item_id=nuevo_id,
            campo="agregado",
            valor_antes=None,
            valor_despues={k: _json(v) for k, v in valores.items() if k != "concepto_id"},
            texto_original=valores.get("texto_original"),
        )
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
        actual = await repo.item_por_id(item_id, version_id)
        if not await repo.borrar_item(item_id, version_id):
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)
        await repo.registrar_correccion(
            version_id=version_id,
            item_id=item_id,
            campo="borrado",
            valor_antes={"cantidad": actual.cantidad} if actual is not None else None,
            valor_despues=None,
            texto_original=actual.texto_original if actual is not None else None,
        )


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


async def _aprobar(repo: RepoAdmin, version_id: uuid.UUID, cabeza: Any) -> None:
    from datetime import UTC, datetime

    await repo.marcar_revisada(version_id, datetime.now(UTC))

    await repo.desvigar_versiones(cabeza.lista_id)
    await repo.promover_vigente(version_id)

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

    tarea = await repo.tarea_para_evento(version_id)
    contacto = tarea.contacto_referencia if tarea is not None else None
    if contacto is not None:
        await repo.emitir_evento(
            tipo="lista_verificada",
            agregado_tipo="version_lista_oficial",
            agregado_id=version_id,
            carga={
                "contacto_referencia": str(contacto),
                "colegio_id": str(cabeza.colegio_id),
                "grado": cabeza.grado,
                "anio_lectivo": cabeza.anio_lectivo,
                "preferencias": tarea.preferencias or {},
                "referencias": list(tarea.referencias or ()),
            },
        )

    if tarea is not None and tarea.colegio_datos:
        datos = dict(tarea.colegio_datos)
        await repo.emitir_evento(
            tipo="colegio_verificado",
            agregado_tipo="colegio",
            agregado_id=cabeza.colegio_id,
            carga={
                "colegio_id": str(cabeza.colegio_id),
                "grado": cabeza.grado,
                "contacto_referencia": None if contacto is None else str(contacto),
                "nombre": datos.get("nombre"),
                "nit": datos.get("dane") or datos.get("nit"),
                "logo_url": datos.get("logo_url"),
                "sitio_web": datos.get("sitio_web"),
                "direccion": datos.get("direccion"),
                "contacto_nombre": datos.get("contacto_nombre"),
                "contacto_email": datos.get("contacto_email"),
                "contacto_telefono": datos.get("contacto_telefono"),
            },
        )


@router.get("/correcciones", summary="Lo que el equipo corrigio en la cola y lo que el sistema aprendio")
async def listar_correcciones(
    campo: Annotated[str | None, Query(max_length=24)] = None,
    limite: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    async with _motor().sesion() as db:
        repo = RepoAdmin(await db.connection())
        filas = await repo.correcciones(campo=campo, limite=limite)
        por_campo = await repo.correcciones_por_campo()
    return {
        "correcciones": [
            {
                "version_id": str(f.version_id),
                "item_id": str(f.item_id) if f.item_id else None,
                "campo": f.campo,
                "valor_antes": f.valor_antes,
                "valor_despues": f.valor_despues,
                "texto_original": f.texto_original,
                "aprendido": f.aprendido,
                "creado_en": f.creado_en.isoformat() if f.creado_en else None,
            }
            for f in filas
        ],
        "por_campo": por_campo,
        "sinonimos_aprendidos": sum(1 for f in filas if f.aprendido),
    }


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
        abiertos = _avisos_de(await _renglones_resueltos(repo, version_id))
        por_item: dict[uuid.UUID, list[str]] = {}
        for aviso in abiertos:
            por_item.setdefault(uuid.UUID(aviso["item_id"]), []).append(aviso["clave"])
        cerrados = await repo.cerrar_avisos_de_version(version_id, por_item)
        for aviso in abiertos:
            await repo.registrar_correccion(
                version_id=version_id,
                item_id=uuid.UUID(aviso["item_id"]),
                campo="aviso",
                valor_antes=aviso["clave"],
                valor_despues="cerrado_al_aprobar",
                texto_original=aviso["texto"],
            )
        await _aprobar(repo, version_id, cabeza)
    return {"version_id": str(version_id), "revisada": True, "avisos_cerrados": cerrados}


async def _clonar_vigente(repo: RepoAdmin, lista: Any, vigente: Any) -> tuple[uuid.UUID, int]:
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

        nuevo_id, nuevo_numero = await _clonar_vigente(repo, lista, vigente)
    return {"version_id": str(nuevo_id), "numero": nuevo_numero, "revisada": False}


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
        await repo.registrar_correccion(
            version_id=version_id,
            item_id=item_id,
            campo="aviso",
            valor_antes=clave,
            valor_despues="descartado",
        )
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
    discriminantes = _nombres_de_atributo(cuerpo.get("atributos_discriminantes"))
    descriptivos = [
        a for a in _nombres_de_atributo(cuerpo.get("atributos_descriptivos")) if a not in discriminantes
    ]

    from ..cargador import _uuid_estable

    async with _motor().engine.begin() as conexion:
        repo = RepoAdmin(conexion)
        ya = await repo.concepto_codigo_por_nombre(nombre.lower())
        if ya is not None:
            raise ErrorDominio(
                "concepto_ya_existe",
                f"Ya existe un concepto '{nombre}' ({ya}). Agregale productos en vez de duplicarlo.",
                estado=409,
                campo="nombre_canonico",
            )
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

    overrides: dict[str, Any] = {}
    if isinstance(cuerpo.get("nombre"), str) and cuerpo["nombre"].strip():
        overrides["nombre"] = cuerpo["nombre"]
    for campo in ("marca", "imagen_url", "personaje"):
        if campo in cuerpo:
            valor = cuerpo[campo]
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
