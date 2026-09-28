"""La superficie de ESCRITURA de la revision de listas, sobre HTTP.

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
edita ni reabre. La decision es la misma funcion (`exigir_sin_revisar`), no una
copia. Editar un renglon, agregarlo o quitarlo solo se permite sobre una
version sin revisar; `cerrar` exige que no queden propuestas sin decidir; y
`nueva-version` clona la vigente en una nueva SIN revisar para poder corregir
una lista ya publicada sin borrar contra que compro quien ya compro.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import and_, delete, func, select, update
from tukit_comun.http import ErrorDominio

from .descubrir import clasificar
from .dominio.listas import (
    _cuidar_invariantes,
    _exigir_sin_revisar,
    _item_publico,
    _pagina_percepcion,
)
from .modelos import Base
from .modelos.base import ModoAdquisicion, TipoItem, UnidadBase

router = APIRouter(prefix="/v1/admin", tags=["admin"])

CONCEPTO = Base.metadata.tables["concepto"]
LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
ITEM = Base.metadata.tables["item_lista_oficial"]
PROPUESTA = Base.metadata.tables["propuesta_producto"]
TAREA = Base.metadata.tables["tarea_importacion"]
TIENDA = Base.metadata.tables["tienda"]
BANDEJA = Base.metadata.tables["bandeja_salida"]

# Las tiendas con busqueda en vivo (VTEX/Shopify), las mismas que usa `admin`.
_SLUGS_TIENDA = {"exito", "panamericana", "grancentral"}

# El mismo corte que usa el cargador de listas (UMBRAL_CONCEPTO): por debajo, el
# renglon queda sin concepto y va a revision en vez de forzarse al mas parecido.
UMBRAL_CONCEPTO = 0.5

_TIPOS_ITEM = {t.value for t in TipoItem}
_MODOS = {m.value for m in ModoAdquisicion}
_UNIDADES = {u.value for u in UnidadBase}


def _motor() -> Any:
    from .api import app

    return app.state.motor


async def _version_y_lista(conexion: Any, version_id: uuid.UUID) -> Any:
    """La cabecera de una version con el grado/colegio de su lista, o None."""
    return (
        await conexion.execute(
            select(
                VERSION.c.id,
                VERSION.c.numero,
                VERSION.c.revisada_en,
                VERSION.c.lista_id,
                LISTA.c.colegio_id,
                LISTA.c.grado,
                LISTA.c.anio_lectivo,
            )
            .select_from(VERSION.join(LISTA, LISTA.c.id == VERSION.c.lista_id))
            .where(VERSION.c.id == version_id)
        )
    ).first()


async def _colegio_datos_de(conexion: Any, version_id: uuid.UUID) -> dict[str, Any] | None:
    """Los `colegio_datos` de la tarea mas reciente de una version, o None.

    Los trae la tarea de importacion (no la version) porque son un hecho del
    proceso —el colegio que se dara de alta al aprobar—, no del contenido
    publicado. Una version de colegio ya aliado no tiene, y devuelve None.
    """
    fila = (
        await conexion.execute(
            select(TAREA.c.colegio_datos)
            .where(TAREA.c.version_id == version_id)
            .order_by(TAREA.c.creada_en.desc())
            .limit(1)
        )
    ).first()
    if fila is None or fila.colegio_datos is None:
        return None
    return dict(fila.colegio_datos)




async def _concepto_id(conexion: Any, codigo: str) -> uuid.UUID:
    cid = (
        await conexion.execute(select(CONCEPTO.c.id).where(CONCEPTO.c.codigo == codigo))
    ).scalar_one_or_none()
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
    ultimo_numero = (
        select(func.max(VERSION.c.numero))
        .where(VERSION.c.lista_id == LISTA.c.id)
        .correlate(LISTA)
        .scalar_subquery()
    )
    items_por_version = (
        select(ITEM.c.version_id.label("vid"), func.count().label("renglones"))
        .group_by(ITEM.c.version_id)
        .subquery()
    )
    # La procedencia y si hay un padre esperando salen de la `tarea_importacion`
    # que produjo la version, no de la version misma: onboarding y
    # sugerencia_padre son hechos del PROCESO de importacion. Se leen como
    # subconsultas correlacionadas —la mas reciente por version— para que una
    # version sin tarea de contexto quede en null/false sin multiplicar filas
    # ni excluirse del listado.
    tarea_reciente = (
        select(TAREA.c.id)
        .where(TAREA.c.version_id == VERSION.c.id)
        .order_by(TAREA.c.creada_en.desc())
        .limit(1)
        .correlate(VERSION)
        .scalar_subquery()
    )
    procedencia = (
        select(TAREA.c.origen).where(TAREA.c.id == tarea_reciente).scalar_subquery()
    )
    contacto = (
        select(TAREA.c.contacto_referencia)
        .where(TAREA.c.id == tarea_reciente)
        .scalar_subquery()
    )
    # Los datos del colegio NUEVO que el acudiente escribio/eligio, cuando el
    # colegio aun no existe en Tukit (no hay fila en `colegio` que darle nombre).
    # Viajan en `colegio_datos` de la tarea; el nombre se extrae en Python (JSON
    # generico, portable a SQLite) para que la cola muestre "Colegio X" en vez
    # del id derivado. Un colegio aliado ya conocido no los trae.
    colegio_datos = (
        select(TAREA.c.colegio_datos)
        .where(TAREA.c.id == tarea_reciente)
        .scalar_subquery()
    )
    consulta = (
        select(
            LISTA.c.id.label("lista_id"),
            LISTA.c.colegio_id,
            LISTA.c.grado,
            LISTA.c.anio_lectivo,
            VERSION.c.id.label("version_id"),
            VERSION.c.numero,
            VERSION.c.revisada_en,
            func.coalesce(items_por_version.c.renglones, 0).label("renglones"),
            procedencia.label("procedencia"),
            contacto.label("contacto_referencia"),
            colegio_datos.label("colegio_datos"),
        )
        .select_from(
            LISTA.join(
                VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.numero == ultimo_numero)
            ).outerjoin(items_por_version, items_por_version.c.vid == VERSION.c.id)
        )
    )
    if revisada is True:
        consulta = consulta.where(VERSION.c.revisada_en.is_not(None))
    elif revisada is False:
        consulta = consulta.where(VERSION.c.revisada_en.is_(None))
    if colegio_id is not None:
        consulta = consulta.where(LISTA.c.colegio_id == colegio_id)
    if grado:
        consulta = consulta.where(LISTA.c.grado == grado)
    if anio_lectivo is not None:
        consulta = consulta.where(LISTA.c.anio_lectivo == anio_lectivo)
    consulta = consulta.order_by(VERSION.c.revisada_en.is_(None).desc(), LISTA.c.grado)

    async with _motor().engine.begin() as conexion:
        filas = await conexion.execute(consulta)
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
                "colegio_nombre": (
                    (f.colegio_datos or {}).get("nombre") if f.colegio_datos else None
                ),
            }
            for f in filas
        ]
    return {"total": len(datos), "listas": datos}


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
        cabeza = await _version_y_lista(conexion, version_id)
        if cabeza is None:
            raise ErrorDominio(
                "version_no_existe",
                "No hay ninguna version con ese identificador.",
                estado=404,
            )
        filas = await conexion.execute(
            select(
                ITEM.c.id,
                ITEM.c.orden,
                ITEM.c.texto_original,
                ITEM.c.cantidad,
                ITEM.c.unidad,
                ITEM.c.tipo_item,
                ITEM.c.modo_adquisicion,
                ITEM.c.instruccion_colegio,
                ITEM.c.url_externa,
                ITEM.c.atributos,
                ITEM.c.requiere_revision,
                CONCEPTO.c.codigo.label("concepto_codigo"),
                CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
            )
            .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
            .where(ITEM.c.version_id == version_id)
            .order_by(ITEM.c.orden)
        )
        items = [_item_publico(f) for f in filas]

        propuestas = await conexion.execute(
            select(
                PROPUESTA.c.id,
                PROPUESTA.c.texto_origen,
                PROPUESTA.c.item_lista_id,
                PROPUESTA.c.nombre,
                PROPUESTA.c.marca,
                PROPUESTA.c.imagen_url,
                PROPUESTA.c.precio_centavos,
                PROPUESTA.c.nivel_sugerido,
                PROPUESTA.c.concepto_sugerido,
                PROPUESTA.c.puntaje,
                CONCEPTO.c.codigo.label("concepto_codigo"),
                CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
            )
            .select_from(PROPUESTA.outerjoin(CONCEPTO, CONCEPTO.c.id == PROPUESTA.c.concepto_id))
            .where(PROPUESTA.c.version_lista_id == version_id, PROPUESTA.c.estado == "pendiente")
            .order_by(PROPUESTA.c.propuesta_en)
        )
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
            for p in propuestas
        ]

        # Los datos del colegio NUEVO que se dara de alta al aprobar (nombre,
        # dane y lo que el revisor complete). None cuando la lista es de un
        # colegio ya aliado: no hay identidad que crear ni que completar.
        colegio_datos = await _colegio_datos_de(conexion, version_id)

    return {
        "version_id": str(cabeza.id),
        "colegio_id": str(cabeza.colegio_id),
        "grado": cabeza.grado,
        "anio_lectivo": int(cabeza.anio_lectivo),
        "numero": int(cabeza.numero),
        "revisada": cabeza.revisada_en is not None,
        "items": items,
        "propuestas": candidatos,
        "colegio_datos": colegio_datos,
    }


# ---------------------------------------------------------------------------
# La ruta rapida: los renglones resueltos de una version YA revisada con sus
# candidatos curados, keyed por concepto, sin buscar por texto ni recomputar.
# ---------------------------------------------------------------------------


async def _candidatos_por_concepto(conexion: Any, codigos: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Los candidatos curados de un conjunto de conceptos, uno por nivel.

    REUSA el mismo constructor de opciones que `emparejar`: la consulta de
    productos con su precio vigente (`_consulta_productos`) y el corte de una
    opcion por nivel (`_elegir_por_nivel`). La unica diferencia con la ruta de
    emparejar es que aqui se entra por el concepto YA decidido —la lista esta
    revisada— en vez de por busqueda de texto.

    Se piden TODOS los conceptos de la version de una vez y se agrupan en
    memoria por su codigo, para no hacer una consulta por renglon (el patron
    N+1). El dict de salida mapea `concepto_codigo` a la lista de candidatos
    con la forma EXACTA del `Candidato` del optimizador.
    """
    from .consulta import _elegir_por_nivel
    from .repositorios.catalogo import CONCEPTO as _CONCEPTO_API
    from .repositorios.catalogo import _consulta_productos, _precio_minimo_vigente

    if not codigos:
        return {}

    precio_min = _precio_minimo_vigente()
    filas = await conexion.execute(_consulta_productos(precio_min).where(_CONCEPTO_API.c.codigo.in_(codigos)))

    # Se agrupan los productos crudos por concepto en la forma que
    # `_elegir_por_nivel` consume (las mismas llaves que arma `emparejar`).
    por_concepto: dict[str, list[dict[str, Any]]] = {}
    for f in filas:
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

    salida: dict[Any, list[dict[str, Any]]] = {}
    for concepto_id, productos in por_concepto.items():
        salida[concepto_id] = [
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
                # La lista ya esta revisada: no hay atributo impuesto que filtrar,
                # asi que todo candidato curado del concepto cumple.
                "cumple": True,
            }
            for p in _elegir_por_nivel(productos)
        ]
    return salida


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
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
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

        filas = list(
            await conexion.execute(
                select(
                    ITEM.c.id,
                    ITEM.c.orden,
                    ITEM.c.texto_original,
                    ITEM.c.cantidad,
                    ITEM.c.tipo_item,
                    ITEM.c.modo_adquisicion,
                    ITEM.c.instruccion_colegio,
                    ITEM.c.url_externa,
                    ITEM.c.concepto_id,
                    CONCEPTO.c.codigo.label("concepto_codigo"),
                    CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                )
                .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
                .where(ITEM.c.version_id == version_id)
                .order_by(ITEM.c.orden)
            )
        )

        codigos = sorted({f.concepto_codigo for f in filas if f.concepto_codigo is not None})
        candidatos_por_concepto = await _candidatos_por_concepto(conexion, codigos)

        items = [
            {
                "item_id": str(f.id),
                "orden": int(f.orden),
                "texto_original": f.texto_original,
                "cantidad": int(f.cantidad),
                "tipo_item": f.tipo_item,
                "modo_adquisicion": f.modo_adquisicion,
                "concepto_codigo": f.concepto_codigo,
                "concepto_nombre": f.concepto_nombre,
                "instruccion_colegio": f.instruccion_colegio,
                "url_externa": f.url_externa,
                "candidatos": (
                    candidatos_por_concepto.get(f.concepto_codigo, [])
                    if f.concepto_codigo is not None
                    else []
                ),
            }
            for f in filas
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


async def _cargar_conceptos(conexion: Any) -> list[dict[str, Any]]:
    """El vocabulario activo, con la MISMA forma que `descubrir.leer_conceptos`.

    Se lee una vez por importacion y se pasa a `clasificar` renglon a renglon,
    igual que hace el cargador de listas, para que la resolucion sea identica a
    la del CLI y no una segunda implementacion que derive.
    """
    filas = await conexion.execute(
        select(CONCEPTO.c.id, CONCEPTO.c.nombre_canonico, CONCEPTO.c.sinonimos).where(CONCEPTO.c.activo)
    )
    return [{"id": f.id, "nombre": f.nombre_canonico, "sinonimos": list(f.sinonimos or ())} for f in filas]


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

    async with _motor().sesion() as db:
        conexion = await db.connection()

        # Resolver o crear la lista para (colegio, grado, ano). El indice unico
        # de la lista incluye sede_id; onboarding no la maneja, asi que va NULL.
        lista = (
            await conexion.execute(
                select(LISTA.c.id).where(
                    LISTA.c.colegio_id == colegio_id,
                    LISTA.c.grado == grado,
                    LISTA.c.anio_lectivo == anio_lectivo,
                )
            )
        ).first()
        if lista is None:
            lista_id = uuid.uuid4()
            await conexion.execute(
                LISTA.insert().values(
                    id=lista_id, colegio_id=colegio_id, grado=grado, anio_lectivo=anio_lectivo
                )
            )
        else:
            lista_id = lista.id

        # El siguiente numero, y quitarle la vigencia a la anterior ANTES de
        # insertar la nueva, para no violar el indice de una sola vigente.
        ultimo = (
            await conexion.execute(select(func.max(VERSION.c.numero)).where(VERSION.c.lista_id == lista_id))
        ).scalar_one_or_none()
        numero = int(ultimo or 0) + 1
        await conexion.execute(
            update(VERSION)
            .where(VERSION.c.lista_id == lista_id, VERSION.c.vigente.is_(True))
            .values(vigente=False)
        )
        version_id = uuid.uuid4()
        await conexion.execute(
            VERSION.insert().values(
                id=version_id, lista_id=lista_id, numero=numero, vigente=True, revisada_en=None
            )
        )

        conceptos = await _cargar_conceptos(conexion)
        for orden, renglon in enumerate(renglones, start=1):
            concepto_id, _nombre, parecido = clasificar(renglon["texto"], conceptos)
            if parecido < UMBRAL_CONCEPTO:
                concepto_id = None
            await conexion.execute(
                ITEM.insert().values(
                    id=uuid.uuid4(),
                    version_id=version_id,
                    orden=orden,
                    texto_original=renglon["texto"],
                    concepto_id=concepto_id,
                    cantidad=renglon["cantidad"],
                    requiere_revision=concepto_id is None,
                    confianza_normalizacion=renglon["confianza"],
                )
            )

        tarea_id = uuid.uuid4()
        await conexion.execute(
            TAREA.insert().values(
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
            )
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
        conexion = await db.connection()
        await conexion.execute(
            TAREA.insert().values(
                id=tarea_id,
                origen="sugerencia_padre",
                estado="pendiente",
                colegio_id=colegio_id,
                grado=grado,
                anio_lectivo=anio_lectivo,
                contacto_referencia=contacto_referencia,
                documento=documento,
            )
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
    consulta = (
        select(
            TAREA.c.id,
            TAREA.c.estado,
            TAREA.c.colegio_id,
            TAREA.c.grado,
            TAREA.c.anio_lectivo,
            TAREA.c.contacto_referencia,
            TAREA.c.documento.is_not(None).label("tiene_documento"),
        )
        .where(TAREA.c.origen == "sugerencia_padre")
        .order_by(TAREA.c.creada_en.desc())
    )
    async with _motor().engine.begin() as conexion:
        filas = await conexion.execute(consulta)
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




async def _tarea_con_evidencia(conexion: Any, version_id: uuid.UUID) -> Any:
    """La tarea de importacion que dejo la evidencia de esta version, o None.

    No filtra por `origen`: la evidencia (PDF + percepcion) la deja tanto la
    subida del colegio ('onboarding') como la del acudiente ('sugerencia_padre').
    Se toma la mas reciente por version, que es la que produjo la vigente.
    """
    return (
        await conexion.execute(
            select(TAREA.c.documento, TAREA.c.percepcion_cruda)
            .where(TAREA.c.version_id == version_id)
            .order_by(TAREA.c.creada_en.desc())
        )
    ).first()


@router.get(
    "/listas/{version_id}/documento",
    summary="El PDF original que dio lugar a esta version (region 1)",
)
async def documento_de_version(version_id: uuid.UUID) -> Response:
    async with _motor().engine.begin() as conexion:
        tarea = await _tarea_con_evidencia(conexion, version_id)
        if tarea is None or tarea.documento is None:
            raise ErrorDominio(
                "sin_evidencia",
                "Esta version no tiene un documento de origen.",
                estado=404,
            )
        return Response(content=bytes(tarea.documento), media_type="application/pdf")


@router.get(
    "/listas/{version_id}/percepcion",
    summary="Lo que la percepcion leyo por pagina y los renglones resultantes (region 2)",
)
async def percepcion_de_version(version_id: uuid.UUID) -> dict[str, Any]:
    async with _motor().engine.begin() as conexion:
        tarea = await _tarea_con_evidencia(conexion, version_id)
        if tarea is None:
            raise ErrorDominio(
                "sin_evidencia",
                "Esta version no tiene percepcion de origen.",
                estado=404,
            )
        filas = await conexion.execute(
            select(ITEM.c.texto_original, ITEM.c.cantidad, ITEM.c.confianza_normalizacion)
            .where(ITEM.c.version_id == version_id)
            .order_by(ITEM.c.orden)
        )
        items = [
            {
                "texto_original": f.texto_original,
                "cantidad": int(f.cantidad),
                "confianza": None if f.confianza_normalizacion is None else float(f.confianza_normalizacion),
            }
            for f in filas
        ]
    return {
        "version_id": str(version_id),
        "paginas": [_pagina_percepcion(p) for p in (tarea.percepcion_cruda or [])],
        "items": items,
    }


# ---------------------------------------------------------------------------
# Editar los renglones (solo sobre una version sin revisar)
# ---------------------------------------------------------------------------


async def _valores_de_renglon(conexion: Any, cuerpo: dict[str, Any], *, nuevo: bool) -> dict[str, Any]:
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
            if valor is not None and valor not in permitidos:
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
        valores["atributos"] = dict(cuerpo["atributos"] or {})
    if "concepto_codigo" in cuerpo:
        codigo = cuerpo["concepto_codigo"]
        valores["concepto_id"] = None if codigo is None else await _concepto_id(conexion, codigo)
    if "requiere_revision" in cuerpo:
        valores["requiere_revision"] = bool(cuerpo["requiere_revision"])
    return valores




@router.patch(
    "/listas/{version_id}/items/{item_id}",
    summary="Editar un renglon de una version sin revisar",
)
async def editar_item(version_id: uuid.UUID, item_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    async with _motor().sesion() as db:
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        _exigir_sin_revisar(cabeza)
        actual = (
            await conexion.execute(select(ITEM).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id))
        ).first()
        if actual is None:
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)

        valores = await _valores_de_renglon(conexion, cuerpo, nuevo=False)
        concepto_id = valores.get("concepto_id", actual.concepto_id)
        requiere = valores.get("requiere_revision", actual.requiere_revision)
        modo = valores.get("modo_adquisicion", actual.modo_adquisicion)
        instruccion = valores.get("instruccion_colegio", actual.instruccion_colegio)
        _cuidar_invariantes(concepto_id, requiere, modo, instruccion)
        if valores:
            await conexion.execute(update(ITEM).where(ITEM.c.id == item_id).values(**valores))
    return {"item_id": str(item_id), "actualizado": True}


@router.post(
    "/listas/{version_id}/items",
    status_code=201,
    summary="Agregar un renglon a una version sin revisar",
)
async def agregar_item(version_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    async with _motor().sesion() as db:
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        _exigir_sin_revisar(cabeza)

        valores = await _valores_de_renglon(conexion, cuerpo, nuevo=True)
        concepto_id = valores.get("concepto_id")
        requiere = valores.get("requiere_revision", concepto_id is None)
        valores["requiere_revision"] = requiere
        _cuidar_invariantes(
            concepto_id,
            requiere,
            valores.get("modo_adquisicion"),
            valores.get("instruccion_colegio"),
        )

        # El siguiente orden libre: el ultimo mas uno, para no chocar con el
        # indice unico (version_id, orden).
        ultimo = (
            await conexion.execute(select(func.max(ITEM.c.orden)).where(ITEM.c.version_id == version_id))
        ).scalar_one_or_none()
        orden = int(ultimo or 0) + 1
        nuevo_id = uuid.uuid4()
        await conexion.execute(
            ITEM.insert().values(id=nuevo_id, version_id=version_id, orden=orden, **valores)
        )
    return {"item_id": str(nuevo_id), "orden": orden}


@router.delete(
    "/listas/{version_id}/items/{item_id}",
    status_code=204,
    summary="Quitar un renglon de una version sin revisar",
)
async def quitar_item(version_id: uuid.UUID, item_id: uuid.UUID) -> None:
    async with _motor().sesion() as db:
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        _exigir_sin_revisar(cabeza)
        resultado = await conexion.execute(
            delete(ITEM).where(ITEM.c.id == item_id, ITEM.c.version_id == version_id)
        )
        if not resultado.rowcount:
            raise ErrorDominio("item_no_existe", "Ese renglon no esta en esta version.", estado=404)


@router.delete(
    "/listas/{version_id}",
    status_code=204,
    summary="Descartar una version sin revisar de la cola",
)
async def borrar_version(version_id: uuid.UUID) -> None:
    """Sacar de la cola una version que aun no se aprueba (una sugerencia que
    no va, un onboarding equivocado). Solo SIN revisar: una version revisada es
    la lista oficial del colegio y no se borra —se corrige con una nueva—, misma
    puerta que editar. Los renglones y las propuestas caen por CASCADE; la tarea
    de importacion queda (su `version_id` es SET NULL) como rastro de que se subio.
    """
    async with _motor().sesion() as db:
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        _exigir_sin_revisar(cabeza)
        await conexion.execute(delete(VERSION).where(VERSION.c.id == version_id))


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
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        _exigir_sin_revisar(cabeza)

        tarea = (
            await conexion.execute(
                select(TAREA.c.id, TAREA.c.colegio_datos)
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()
        if tarea is None or tarea.colegio_datos is None:
            raise ErrorDominio(
                "sin_colegio_por_crear",
                "Esta lista es de un colegio ya aliado: no hay un colegio nuevo que completar.",
                estado=409,
            )

        datos = dict(tarea.colegio_datos)
        datos.update(parche)
        await conexion.execute(
            update(TAREA).where(TAREA.c.id == tarea.id).values(colegio_datos=datos)
        )
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
        conexion = await db.connection()
        fila = (
            await conexion.execute(
                select(PROPUESTA.c.id, PROPUESTA.c.estado).where(PROPUESTA.c.id == prop_id)
            )
        ).first()
        if fila is None:
            raise ErrorDominio(
                "propuesta_no_existe",
                "No hay ninguna propuesta con ese identificador.",
                estado=404,
            )
        if fila.estado != "pendiente":
            raise ErrorDominio("propuesta_ya_resuelta", f"Esa propuesta ya esta {fila.estado}.", estado=409)
        await conexion.execute(
            update(PROPUESTA)
            .where(PROPUESTA.c.id == prop_id)
            .values(estado="rechazada", motivo=motivo, resuelta_en=datetime.now(UTC))
        )
    return {"id": str(prop_id), "estado": "rechazada"}


# ---------------------------------------------------------------------------
# Cerrar (aprobar) y nueva version (corregir)
# ---------------------------------------------------------------------------


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
    from datetime import UTC, datetime

    async with _motor().sesion() as db:
        conexion = await db.connection()
        cabeza = await _version_y_lista(conexion, version_id)
        if cabeza is None:
            raise ErrorDominio(
                "version_no_existe",
                "No hay ninguna version con ese identificador.",
                estado=404,
            )
        if cabeza.revisada_en is not None:
            return {"version_id": str(version_id), "revisada": True, "ya_estaba": True}
        pendientes = (
            await conexion.execute(
                select(func.count())
                .select_from(PROPUESTA)
                .where(PROPUESTA.c.version_lista_id == version_id, PROPUESTA.c.estado == "pendiente")
            )
        ).scalar_one()
        if pendientes:
            raise ErrorDominio(
                "propuestas_pendientes",
                f"Quedan {pendientes} propuestas sin decidir. Resuelvelas antes de cerrar.",
                estado=409,
            )
        await conexion.execute(
            update(VERSION).where(VERSION.c.id == version_id).values(revisada_en=datetime.now(UTC))
        )

        # Aprobar es lo que le pasa la vigencia a esta version: al editar, el
        # borrador nacio SIN vigencia para que el acudiente siguiera viendo la
        # anterior; ahora que se aprueba, se degrada la vigente actual y se
        # promueve esta, en ESTA misma transaccion, para respetar el indice
        # parcial de una sola vigente por lista. Es no-op en el onboarding de
        # estreno: la version aprobada ya era la unica vigente (se degrada y se
        # re-promueve la misma fila).
        await conexion.execute(
            update(VERSION)
            .where(VERSION.c.lista_id == cabeza.lista_id, VERSION.c.vigente.is_(True))
            .values(vigente=False)
        )
        await conexion.execute(update(VERSION).where(VERSION.c.id == version_id).values(vigente=True))

        # Si un padre estaba esperando esta version (subio su PDF y quedo ligado
        # por `contacto_referencia`), aprobarla dispara su kit. Pero Catalogo NO
        # llama a Inteligencia —esa arista cerraria un ciclo en el grafo de
        # dependencias, la misma razon por la que esta tabla no tiene `caso_id`—:
        # se escribe un evento `lista_verificada` en la bandeja de salida, EN LA
        # MISMA transaccion que el `revisada_en`, y un poller de Inteligencia lo
        # drena y arma el trabajo de ruta rapida con las preferencias guardadas.
        # El onboarding del colegio no deja padre esperando: no emite nada.
        tarea = (
            await conexion.execute(
                select(
                    TAREA.c.id,
                    TAREA.c.contacto_referencia,
                    TAREA.c.preferencias,
                    TAREA.c.colegio_datos,
                )
                .where(TAREA.c.version_id == version_id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()
        if tarea is not None and tarea.contacto_referencia is not None:
            await conexion.execute(
                BANDEJA.insert().values(
                    tipo="lista_verificada",
                    agregado_tipo="version_lista_oficial",
                    agregado_id=version_id,
                    carga={
                        # El padre, por identificador; NUNCA su correo/telefono.
                        "contacto_referencia": str(tarea.contacto_referencia),
                        "colegio_id": str(cabeza.colegio_id),
                        "grado": cabeza.grado,
                        "anio_lectivo": cabeza.anio_lectivo,
                        # Lo que el padre pidio en el paso 3, para optimizar su kit.
                        "preferencias": tarea.preferencias,
                    },
                )
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
            await conexion.execute(
                BANDEJA.insert().values(
                    tipo="colegio_verificado",
                    agregado_tipo="colegio",
                    agregado_id=cabeza.colegio_id,
                    carga={
                        "colegio_id": str(cabeza.colegio_id),
                        "grado": cabeza.grado,
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
            )
    return {"version_id": str(version_id), "revisada": True}


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
        conexion = await db.connection()
        lista = (
            await conexion.execute(
                select(LISTA.c.id).where(
                    LISTA.c.colegio_id == colegio_id,
                    LISTA.c.grado == grado,
                    LISTA.c.anio_lectivo == anio_lectivo,
                )
            )
        ).first()
        if lista is None:
            raise ErrorDominio(
                "lista_no_existe",
                "No hay ninguna lista para ese colegio, grado y ano.",
                estado=404,
            )

        vigente = (
            await conexion.execute(
                select(VERSION.c.id, VERSION.c.numero, VERSION.c.revisada_en).where(
                    VERSION.c.lista_id == lista.id, VERSION.c.vigente.is_(True)
                )
            )
        ).first()
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
        siguiente = (
            await conexion.execute(
                select(func.max(VERSION.c.numero)).where(VERSION.c.lista_id == lista.id)
            )
        ).scalar_one_or_none()
        nuevo_numero = int(siguiente or 0) + 1
        nuevo_id = uuid.uuid4()
        await conexion.execute(
            VERSION.insert().values(
                id=nuevo_id, lista_id=lista.id, numero=nuevo_numero, vigente=False, revisada_en=None
            )
        )
        renglones = await conexion.execute(
            select(
                ITEM.c.orden,
                ITEM.c.texto_original,
                ITEM.c.concepto_id,
                ITEM.c.cantidad,
                ITEM.c.unidad,
                ITEM.c.tipo_item,
                ITEM.c.modo_adquisicion,
                ITEM.c.instruccion_colegio,
                ITEM.c.url_externa,
                ITEM.c.atributos,
                ITEM.c.requiere_revision,
            ).where(ITEM.c.version_id == vigente.id)
        )
        for r in renglones:
            await conexion.execute(
                ITEM.insert().values(
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
                )
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
        origen_tarea = (
            await conexion.execute(
                select(
                    TAREA.c.origen,
                    TAREA.c.documento,
                    TAREA.c.percepcion_cruda,
                    TAREA.c.colegio_datos,
                    TAREA.c.colegio_id,
                    TAREA.c.grado,
                    TAREA.c.anio_lectivo,
                )
                .where(TAREA.c.version_id == vigente.id)
                .order_by(TAREA.c.creada_en.desc())
                .limit(1)
            )
        ).first()
        if origen_tarea is not None:
            await conexion.execute(
                TAREA.insert().values(
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
            )
    return {"version_id": str(nuevo_id), "numero": nuevo_numero, "revisada": False}


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
    consulta = (
        select(
            PROPUESTA.c.id,
            PROPUESTA.c.texto_origen,
            PROPUESTA.c.nombre,
            PROPUESTA.c.marca,
            PROPUESTA.c.imagen_url,
            PROPUESTA.c.precio_centavos,
            PROPUESTA.c.nivel_sugerido,
            PROPUESTA.c.concepto_sugerido,
            PROPUESTA.c.puntaje,
            PROPUESTA.c.origen,
            CONCEPTO.c.codigo.label("concepto_codigo"),
            CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
        )
        .select_from(PROPUESTA.outerjoin(CONCEPTO, CONCEPTO.c.id == PROPUESTA.c.concepto_id))
        .where(PROPUESTA.c.estado == "pendiente")
        .order_by(PROPUESTA.c.propuesta_en)
    )
    if concepto:
        consulta = consulta.where(CONCEPTO.c.codigo == concepto)

    async with _motor().engine.begin() as conexion:
        filas = await conexion.execute(consulta)
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
            }
            for p in filas
        ]
    return {"total": len(propuestas), "propuestas": propuestas}


async def _tienda_id_por_slug(conexion: Any, slug: str) -> uuid.UUID | None:
    """El id de una tienda por su slug, dentro de la conexion abierta.

    Gemelo de `admin._tienda_por_slug`, pero sobre el motor del servicio en vez
    de abrir uno propio: el alta necesita el `tienda_id` para colgar la oferta
    en la tienda correcta.
    """
    return (
        await conexion.execute(select(TIENDA.c.id).where(TIENDA.c.slug == slug))
    ).scalar_one_or_none()


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

    from . import tiendas

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

    from .cargador import _uuid_estable

    async with _motor().engine.begin() as conexion:
        # El nombre canonico ya existente es el choque real: dos "cuaderno" con
        # codigos distintos partirian el vocabulario del matcher. El codigo se
        # autogenera, asi que no puede chocar.
        ya = (
            await conexion.execute(
                select(CONCEPTO.c.codigo).where(func.lower(CONCEPTO.c.nombre_canonico) == nombre.lower())
            )
        ).scalar_one_or_none()
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
        codigos = [
            c for (c,) in await conexion.execute(select(CONCEPTO.c.codigo)) if c and c.startswith("C")
        ]
        maximo = max((int(c[1:]) for c in codigos if c[1:].isdigit()), default=0)
        codigo = f"C{maximo + 1:03d}"

        await conexion.execute(
            CONCEPTO.insert().values(
                id=_uuid_estable("concepto", codigo),
                codigo=codigo,
                nombre_canonico=nombre,
                sinonimos=sinonimos,
                categoria=categoria,
                tipo_item=tipo_item,
                admite_personaje=bool(cuerpo.get("admite_personaje", False)),
            )
        )
    return {"codigo": codigo, "nombre_canonico": nombre, "categoria": categoria, "tipo_item": tipo_item}


@router.post(
    "/catalogo/propuestas/util",
    status_code=201,
    summary="Encolar un util elegido de una tienda (encola, NO aprueba)",
)
async def encolar_util(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Encola el candidato elegido; la aprobacion es un paso aparte.

    Re-busca por `(slug, sku)` con `admin.buscar_candidatos` --el mismo camino
    que `admin._util`-- para no confiar en que el navegador arme la Oferta: el
    precio y la ficha salen de la tienda, no del cliente. Si el candidato ya no
    aparece (se agoto entre la busqueda y el alta), es un 422 con causa, no un
    500. El concepto se resuelve por codigo (`concepto_no_existe` si no existe)
    y el dict lo arma `construir_propuesta_util`, que HTTP y CLI comparten.
    """
    from . import admin
    from .descubrir import _encolar
    from .dominio.propuesta import construir_propuesta_util

    consulta = str(cuerpo.get("consulta") or "").strip()
    slug = str(cuerpo.get("slug") or "")
    sku = str(cuerpo.get("sku") or "")
    nivel = str(cuerpo.get("nivel") or "confiable")
    codigo = str(cuerpo.get("concepto") or "")

    elegida = next(
        (o for s, o in admin.buscar_candidatos(consulta) if s == slug and o.sku == sku), None
    )
    if elegida is None:
        raise ErrorDominio(
            "candidato_no_disponible",
            "Ese candidato ya no esta disponible en la tienda; busca de nuevo.",
            estado=422,
            campo="sku",
        )

    async with _motor().engine.begin() as conexion:
        concepto_id = await _concepto_id(conexion, codigo)
        tienda_id = await _tienda_id_por_slug(conexion, slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = (
            await conexion.execute(
                select(CONCEPTO.c.nombre_canonico).where(CONCEPTO.c.id == concepto_id)
            )
        ).scalar_one()

    propuesta = construir_propuesta_util(
        concepto_id, nombre_concepto, slug, tienda_id, elegida, nivel
    )
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
    from . import tiendas
    from .descubrir import _encolar
    from .dominio.propuesta import _uuid_estable, construir_propuesta_util

    codigo = str(cuerpo.get("concepto") or "")
    nombre = str(cuerpo.get("nombre") or "").strip()
    if not nombre:
        raise ErrorDominio(
            "nombre_invalido", "El util necesita un nombre.", estado=422, campo="nombre"
        )
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
        concepto_id = await _concepto_id(conexion, codigo)
        tienda_id = await _tienda_id_por_slug(conexion, slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = (
            await conexion.execute(
                select(CONCEPTO.c.nombre_canonico).where(CONCEPTO.c.id == concepto_id)
            )
        ).scalar_one()

    propuesta = construir_propuesta_util(
        concepto_id, nombre_concepto, slug, tienda_id, oferta, nivel
    )
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
    from .cargador import isbn13_valido, normalizar_isbn
    from .descubrir import _encolar
    from .dominio.propuesta import construir_propuesta_libro

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
        concepto_id = await _concepto_id(conexion, codigo)
        tienda_id = await _tienda_id_por_slug(conexion, slug)
        if tienda_id is None:
            raise ErrorDominio(
                "tienda_desconocida", f"No conozco la tienda '{slug}'.", estado=422, campo="slug"
            )
        nombre_concepto = (
            await conexion.execute(
                select(CONCEPTO.c.nombre_canonico).where(CONCEPTO.c.id == concepto_id)
            )
        ).scalar_one()

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
    from . import descubrir

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
