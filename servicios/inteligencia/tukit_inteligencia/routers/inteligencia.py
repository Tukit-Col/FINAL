"""El adaptador de entrada HTTP de Inteligencia: parsear, orquestar, traducir.

Un solo router que `api.py` monta. Estas rutas parsean la peticion (incluidos
los 422 de forma), llaman al orquestador `trabajos` y a las metricas, y traducen
el resultado o el error de dominio a su sobre HTTP. El wiring (motor, clientes
remotos catalogo/identidad/comercio y los puertos de percepcion) vive en
`api.py` y se alcanza por el modulo `api`: `app` es el mismo singleton, asi que
`api._catalogo()` / `api.app.state.motor` leen lo que las pruebas inyectan por
`app.state`, incluidos los puertos de percepcion (`app.state.renderizar` /
`app.state.leer`) que usa `api._percibir_onboarding` (ADR 0019).
"""

from __future__ import annotations

import base64
import json
import re
import unicodedata
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from tukit_comun import derivar
from tukit_comun.autenticacion import token_bearer
from tukit_comun.http import ErrorDominio

from .. import api, apodos_subida, importaciones, metricas, trabajos
from ..modelos import EstadoResolucion, EstadoTrabajo
from ..percepcion import Percepcion
from ..remoto import RemotoCaido

router = APIRouter()

# Los roles que dan acceso a las vistas del equipo interno. Mismo par que usa
# identidad en `/v1/admin/acudientes` (`_ROLES_STAFF`), y la razon de que esta
# puerta tenga la misma semantica.
_ROLES_STAFF = ("admin", "operador")


async def _exigir_staff(authorization: str | None) -> None:
    """Puerta operador/admin con la MISMA semantica que `/v1/admin/acudientes`:
    401 sin token o con token invalido/revocado, 403 si el rol no es staff.

    Inteligencia no puede leer la base de identidad (invariantes 1 y 3): valida
    por HTTP contra `GET /v1/sesiones/actual`, el chequeo autoritativo que ya
    compara `version_permisos`. Falla CERRADA (503) si identidad no responde:
    no autorizar por no poder preguntar seria abrir el acceso."""
    token = token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    try:
        sesion = await api._identidad().sesion(token)
    except RemotoCaido as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    roles = {r.get("rol") for r in sesion.get("roles", [])}
    if not roles & set(_ROLES_STAFF):
        raise ErrorDominio(
            "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.", estado=403
        )


async def _usuario_de_sesion(authorization: str | None) -> uuid.UUID:
    """Puerta de portador: cualquier sesion valida, sin exigir rol de staff.

    Misma validacion y misma falla CERRADA que `_exigir_staff` (401 sin token o
    con token invalido/revocado, 503 si identidad no responde), pero devuelve el
    `usuario_id` de la sesion en vez de comprobar roles. Es lo que deja que "Mis
    solicitudes" use el id del PORTADOR y nunca uno que venga del navegador."""
    token = token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    try:
        sesion = await api._identidad().sesion(token)
    except RemotoCaido as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    return uuid.UUID(str(sesion["usuario_id"]))


async def _exigir_dueno_del_trabajo(trabajo_id: uuid.UUID, authorization: str | None) -> None:
    """Puerta de lectura de un trabajo del acudiente (hallazgo H4 del control de calidad).

    Un trabajo cuyo dueno tiene clave real solo lo lee la sesion de ese dueno (o
    la del equipo interno): con la sesion de otra cuenta es 404, para no confirmar
    que el id existe. Sin sesion es 401, a proposito: la web lo usa para mandar a
    la madre a /ingresar, y eso deja distinguir un id con dueno con clave de uno
    inexistente; se acepta porque el id es un UUIDv4 aleatorio. Si el dueno es un contacto sin clave (ruta
    rapida con correo) o no hay dueno, el enlace del correo es su unico acceso:
    no puede iniciar sesion, asi que se lee por id, que es un UUIDv4 aleatorio.

    Identidad solo se consulta cuando hace falta decidir; si no responde en ese
    momento la puerta falla CERRADA (503), no abre el kit de una cuenta con clave.
    """
    try:
        propietario = await trabajos.dueno(api.app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    if propietario is None:
        return

    token = token_bearer(authorization)
    sesion: dict[str, Any] | None = None
    if token:
        try:
            sesion = await api._identidad().sesion(token)
        except RemotoCaido:
            # Sin poder validar la sesion solo se sigue si el dueno no tiene clave;
            # la consulta de abajo falla cerrada si identidad sigue caida.
            sesion = None
    if sesion is not None:
        roles = {r.get("rol") for r in sesion.get("roles", [])}
        if roles & set(_ROLES_STAFF) or str(sesion.get("usuario_id")) == str(propietario):
            return

    try:
        con_clave = await api._identidad().tiene_credencial(str(propietario))
    except RemotoCaido as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if not con_clave:
        return
    if sesion is None:
        raise ErrorDominio("sesion_requerida", "Inicia sesion para ver este kit.", estado=401)
    raise ErrorDominio("trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404)


class PercepcionRechazada(ErrorDominio):
    """Un rechazo de percepcion que ademas puede nombrar los grados vistos.

    Reusa el sobre de `ErrorDominio` (mismo manejador, mismo `error`/`mensaje`)
    y solo agrega `grados_detectados` cuando el archivo traia mas de un grado,
    que es la unica pista que ayuda al acudiente a subir la pagina correcta.
    Nunca lleva el contenido del archivo: el sobre dice QUE paso, no QUE se
    subio.
    """

    def __init__(self, error: str, mensaje: str, *, grados_detectados: tuple[str, ...] = ()) -> None:
        super().__init__(error, mensaje, estado=422)
        self.grados_detectados = grados_detectados

    def cuerpo(self) -> dict[str, Any]:
        sobre = super().cuerpo()
        if self.grados_detectados:
            sobre["grados_detectados"] = list(self.grados_detectados)
        return sobre


class Hijo(BaseModel):
    """Un hijo del hogar. `referencia` la pone el acudiente, no el sistema.

    No lleva nombre de menor a proposito: para armar un kit basta con saber
    de que colegio y grado es la lista, y pedir el nombre seria recoger un
    dato de menor que el flujo no necesita. La referencia ("hijo-1") es lo
    que permite devolver las lineas agrupadas.
    """

    referencia: str = Field(min_length=1, max_length=64)
    colegio_id: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int | None = Field(default=None, ge=2020, le=2100)
    # Como llama el acudiente a este hijo (nunca el nombre legal del menor). Solo
    # sirve para rotular el kit. Se recorta y pasa de 40 caracteres se RECHAZA
    # (no se trunca en silencio); vacio es None.
    apodo: str | None = Field(default=None, max_length=40)

    @field_validator("apodo", mode="before")
    @classmethod
    def _recortar_apodo(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v


class Contacto(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    celular: str | None = Field(default=None, max_length=32)


# `{referencia del hijo: [personajes]}`: hasta 10 hijos, 5 personajes por hijo
# y 60 caracteres por personaje. Lo valida `Preferencias` y tambien la subida
# de listas, que recibe las preferencias como JSON crudo.
PersonajePorHijo = Annotated[
    dict[
        Annotated[str, Field(min_length=1, max_length=64)],
        Annotated[list[Annotated[str, Field(min_length=1, max_length=60)]], Field(max_length=5)],
    ],
    Field(max_length=10),
]
_VALIDAR_PERSONAJE_POR_HIJO = TypeAdapter(PersonajePorHijo)


class Preferencias(BaseModel):
    """Lo que el acudiente declara. NO se pide el estrato.

    En las 60 respuestas de la encuesta, 41 son estrato 4: no tiene varianza
    suficiente para segmentar y si es dato sensible del hogar de un menor.
    Como ademas la correlacion intuitiva no existe (el segmento que mas gasta
    es el MENOS dispuesto a pagar sobreprecio), quitarlo no cuesta precision.
    """

    pesos: dict[str, float] | None = None
    # Cota DURA, no una pista. Es el uso mas valioso de la encuesta: convierte
    # una opinion en una restriccion que el optimizador puede imponer.
    presupuesto_por_hijo: int | None = Field(default=None, gt=0)
    disposicion_sobreprecio: float | None = Field(default=None, ge=0, le=1)
    # Con tope por la misma razon que `marcas_excluidas`: lo escribe el
    # navegador, se guarda cifrado en el trabajo y cada nombre distinto es una
    # consulta al catalogo por ancla.
    personaje_por_hijo: PersonajePorHijo | None = None
    # Filtros duros del asistente NL2C: el optimizador los aplica a los
    # candidatos antes de armar el frente. Los mismos limites que `FiltrosDuros`
    # de nl2c, porque este es el borde por el que entra todo lo que viene del
    # navegador y un tope aqui evita listas enormes en la preferencia guardada.
    marcas_excluidas: list[Annotated[str, Field(min_length=1, max_length=40)]] | None = Field(
        default=None, max_length=10
    )
    solo_disponibles: bool | None = None
    dolor_declarado: str | None = Field(default=None, max_length=64)
    # Lo que eligio en el paso 3 de /empezar. `equilibrio` pide el kit `A tu
    # Medida` (ADR 0030); los otros dos solo deciden cual se marca.
    prioridad: str | None = Field(default=None, pattern="^(precio|equilibrio|calidad)$")


class PeticionTrabajo(BaseModel):
    hijos: list[Hijo] = Field(min_length=1)
    contacto: Contacto | None = None
    preferencias: Preferencias | None = None


class DecisionLinea(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    # El contrato TS (`ValidarLinea`) lo llama `nota`; "sin coincidencia" manda
    # `motivo`. Se aceptan los dos para que la nota de validar no se pierda.
    motivo: str | None = Field(default=None, max_length=512, validation_alias=AliasChoices("motivo", "nota"))
    actor: uuid.UUID | None = None


class ProductoEnLinea(BaseModel):
    sku: str = Field(max_length=64)


class DescarteDeLinea(BaseModel):
    descartado: bool = True


class DecisionRevision(BaseModel):
    decision: str = Field(pattern="^(aprobar|devolver)$")
    nota: str | None = Field(default=None, max_length=1024)
    actor: uuid.UUID | None = None


class FijarCanonico(BaseModel):
    nota: str | None = Field(default=None, max_length=1024)
    actor: uuid.UUID | None = None


class AplicarCanonico(BaseModel):
    """La ruta rapida del acudiente: su nivel + personaje sobre la cache bendita."""

    colegio_id: str = Field(max_length=64)
    grado: str = Field(max_length=64)
    anio_lectivo: int = Field(ge=2020, le=2100)
    perfil: str = Field(max_length=16)
    personaje: str | None = Field(default=None, max_length=64)
    # Como llama el acudiente a su hijo (nunca el nombre legal): rotula el kit. Misma
    # regla que en `/v1/trabajos`: se recorta, vacio es None y mas de 40 se rechaza.
    apodo: str | None = Field(default=None, max_length=40)
    usuario_id: uuid.UUID | None = None
    # La cache bendita no guarda la marca de las alternativas ni se re-optimiza, asi
    # que NO puede honrar estos filtros. Se aceptan solo para rechazarlos con un
    # error claro en vez de ignorarlos en silencio: el cliente debe crear un
    # trabajo normal, que si re-optimiza con los filtros.
    marcas_excluidas: list[str] | None = Field(default=None, max_length=10)
    solo_disponibles: bool | None = None

    @field_validator("apodo", mode="before")
    @classmethod
    def _recortar_apodo(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v


class EntregaCheckout(BaseModel):
    """La direccion a la que se entrega. Se COPIA congelada en Comercio (ADR 0015).

    Los opcionales llegan del checkout: `localidad` (una de las 20 de Bogota, por
    nombre) e `indicaciones` (apartamento, torre, interior). Mismos largos que Comercio. Las
    coordenadas (`latitud`/`longitud`) solo cruzan las del pin confirmado en el
    mapa de OpenStreetMap (ADR 0049), juntas y dentro de Colombia. Cualquier otro
    campo desconocido se descarta aqui y no cruza."""

    destinatario: str = Field(min_length=1, max_length=256)
    direccion: str = Field(min_length=1, max_length=512)
    ciudad: str = Field(min_length=1, max_length=128)
    departamento: str | None = Field(default=None, max_length=128)
    indicaciones: str | None = Field(default=None, max_length=512)
    localidad: str | None = Field(default=None, max_length=64)
    latitud: float | None = Field(default=None, ge=-4.3, le=13.6)
    longitud: float | None = Field(default=None, ge=-81.8, le=-66.8)

    @model_validator(mode="after")
    def _coordenadas_completas(self) -> EntregaCheckout:
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("latitud y longitud van juntas")
        return self


class PeticionCheckout(BaseModel):
    """Lo que el navegador manda para pagar: el kit por perfil, correo y direccion.

    Nunca un id de base ni una linea: el trabajo (que Inteligencia si conoce)
    tiene el kit y el `usuario_id`; el navegador solo elige el perfil y a donde
    entregar. Asi el checkout no reintroduce lo que RPO cero saca de la vista.
    """

    perfil: str = Field(max_length=16)
    correo: str = Field(min_length=5, max_length=320)
    entrega: EntregaCheckout
    metodo: str = Field(default="pse", max_length=16)
    url_redireccion: str | None = Field(default=None, max_length=512)


@router.post("/v1/trabajos", tags=["trabajos"], status_code=202, summary="Crea un trabajo y lo encola")
async def crear_trabajo(peticion: PeticionTrabajo, solicitud: Request) -> dict[str, Any]:
    """La peticion es por HOGAR y no por hijo.

    Es lo que hace posible la consolidacion entre hermanos y el reparto de
    empaques: si cada hijo se pidiera aparte, el optimizador no podria ver
    que dos ninos necesitan un borrador cada uno y que una caja de diez sale
    mejor.
    """
    referencias = [hijo.referencia for hijo in peticion.hijos]
    if len(set(referencias)) != len(referencias):
        raise ErrorDominio(
            "referencias_repetidas",
            "Cada hijo necesita una referencia distinta: es con lo que se agrupan sus lineas.",
            campo="hijos",
        )

    pesos = (peticion.preferencias.pesos if peticion.preferencias else None) or {}
    if pesos and abs(sum(pesos.values()) - 1.0) > 0.01:
        raise ErrorDominio(
            "pesos_no_suman_uno",
            "Los pesos de las preferencias tienen que sumar 1.0.",
            estado=422,
            campo="preferencias.pesos",
        )

    hijos = [hijo.model_dump(exclude={"apodo"} if hijo.apodo is None else None) for hijo in peticion.hijos]
    # Sin lista para ningun hijo, el trabajo fallaria al procesarse con este
    # mismo motivo: se dice ahora y no se encola (H-C-03). Un hogar con algun
    # hijo sin lista sigue igual: ese hijo sale anotado en el kit.
    if not await trabajos.alguna_lista_para(api._catalogo(), hijos):
        raise ErrorDominio(
            "sin_lista_oficial",
            "No encontramos la lista oficial publicada para ese colegio y grado. "
            "Sube el archivo de la lista o escoge otro grado.",
            estado=422,
            campo="hijos",
        )

    respuesta = await trabajos.crear(
        api.app.state.motor,
        hijos=hijos,
        contacto=peticion.contacto.model_dump() if peticion.contacto else None,
        preferencias=(peticion.preferencias.model_dump(exclude_none=True) if peticion.preferencias else {}),
        usuario_id=uuid.UUID(uid) if (uid := await api._usuario_de_la_peticion(solicitud)) else None,
        identidad=api._identidad(),
    )
    await trabajos.lanzar(api.app.state.motor, uuid.UUID(respuesta["trabajo_id"]))
    return respuesta


@router.get(
    "/v1/trabajos",
    tags=["trabajos"],
    summary="Mis solicitudes de kit (las del acudiente autenticado)",
)
async def mis_trabajos(solicitud: Request) -> dict[str, Any]:
    """El panel del acudiente: sus solicitudes de kit, no pedidos pagados.

    Se resuelve por el Bearer que reenvia el Route Handler; un anonimo no tiene
    trabajos propios que mostrar, asi que se rechaza (401) en vez de devolver
    los de nadie. La superficie no lleva correo ni nombre de menor.
    """
    uid = await api._usuario_de_la_peticion(solicitud)
    if uid is None:
        raise ErrorDominio("sesion_requerida", "Inicia sesion para ver tus solicitudes.", estado=401)
    trabajos_ = await trabajos.mis_trabajos(api.app.state.motor, usuario_id=uuid.UUID(uid))
    return {"total": len(trabajos_), "trabajos": trabajos_}


@router.get("/v1/trabajos/{trabajo_id}", tags=["trabajos"], summary="Estado, etapas y kits del trabajo")
async def ver_trabajo(
    trabajo_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _exigir_dueno_del_trabajo(trabajo_id, authorization)
    try:
        return await trabajos.ver(api.app.state.motor, trabajo_id, catalogo=api._catalogo())
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@router.put(
    "/v1/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item_id}/producto",
    tags=["trabajos"],
    summary="El acudiente cambia un producto de su kit por una de sus alternativas",
)
async def cambiar_producto_del_acudiente(
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    cuerpo: ProductoEnLinea,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Solo entre lo que la linea ya ofrece (el sugerido o sus alternativas).

    La sesion es opcional porque la ruta rapida admite trabajos sin cuenta; si
    el trabajo tiene dueno, `trabajos` exige que la sesion sea la suya. El
    cambio se guarda en el trabajo del acudiente, nunca en el kit canonico.
    """
    usuario_id = await _usuario_de_sesion(authorization) if token_bearer(authorization) else None
    try:
        return await trabajos.cambiar_producto_del_acudiente(
            api.app.state.motor,
            trabajo_id,
            perfil,
            item_id,
            cuerpo.sku,
            usuario_id=usuario_id,
            catalogo=api._catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese kit no tiene ese renglón.", estado=404) from error
    except trabajos.CambioNoPermitido as error:
        raise ErrorDominio(error.codigo, error.mensaje, estado=error.estado) from error


@router.get(
    "/v1/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item_id}/opciones",
    tags=["trabajos"],
    summary="Los productos del mismo concepto que el acudiente puede elegir para un renglon",
)
async def opciones_de_la_linea(
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _exigir_dueno_del_trabajo(trabajo_id, authorization)
    try:
        return await trabajos.opciones_de_la_linea(
            api.app.state.motor, trabajo_id, perfil, item_id, catalogo=api._catalogo()
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese kit no tiene ese renglón.", estado=404) from error
    except RemotoCaido as error:
        raise ErrorDominio(
            "catalogo_no_disponible", "No pudimos traer más opciones ahora. Intenta de nuevo.", estado=503
        ) from error


@router.put(
    "/v1/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item_id}/descarte",
    tags=["trabajos"],
    summary="El acudiente quita un renglon de su kit (ya lo tiene) o lo vuelve a poner",
)
async def descartar_linea_del_acudiente(
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    cuerpo: DescarteDeLinea,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Mismas reglas de dueno que el cambio de producto; reversible."""
    usuario_id = await _usuario_de_sesion(authorization) if token_bearer(authorization) else None
    try:
        return await trabajos.descartar_linea_del_acudiente(
            api.app.state.motor,
            trabajo_id,
            perfil,
            item_id,
            descartar=cuerpo.descartado,
            usuario_id=usuario_id,
            catalogo=api._catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese kit no tiene ese renglón.", estado=404) from error
    except trabajos.CambioNoPermitido as error:
        raise ErrorDominio(error.codigo, error.mensaje, estado=error.estado) from error


@router.post(
    "/v1/trabajos/{trabajo_id}/cancelar",
    tags=["trabajos"],
    summary="El acudiente cancela una solicitud suya (si no compro el kit)",
)
async def cancelar_solicitud(
    trabajo_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """Exige sesion: solo el dueno cancela, y el `usuario_id` sale del token."""
    usuario_id = await _usuario_de_sesion(authorization)
    try:
        return await trabajos.cancelar_solicitud(
            api.app.state.motor,
            trabajo_id,
            usuario_id=usuario_id,
            token=token_bearer(authorization) or "",
            comercio=api._comercio(),
            catalogo=api._catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ninguna solicitud con ese identificador.", estado=404
        ) from error
    except trabajos.SolicitudNoCancelable as error:
        raise ErrorDominio(error.codigo, error.mensaje, estado=error.estado) from error
    except RemotoCaido as error:
        raise ErrorDominio(
            "servicio_no_disponible",
            "No pudimos confirmar si este kit tiene un pedido; intenta de nuevo en un momento.",
            estado=503,
        ) from error


@router.post(
    "/v1/mis-solicitudes/listas/{tarea_id}/cancelar",
    tags=["trabajos"],
    summary="El acudiente cancela una lista que subio y que aun no tiene kit",
)
async def cancelar_lista_subida(
    tarea_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    usuario_id = await _usuario_de_sesion(authorization)
    try:
        return await trabajos.cancelar_lista_subida(usuario_id, str(tarea_id), catalogo=api._catalogo())
    except RemotoCaido as error:
        raise ErrorDominio(
            "servicio_no_disponible",
            "No pudimos cancelar la lista; intenta de nuevo en un momento.",
            estado=503,
        ) from error


@router.get(
    "/v1/mis-solicitudes",
    tags=["trabajos"],
    summary="Las solicitudes del acudiente (listas subidas + trabajos), unidas",
)
async def mis_solicitudes(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """El panel del acudiente: sus listas subidas y sus trabajos, en una lista.

    Exige una sesion valida (no rol de staff) y usa el `usuario_id` de esa
    sesion; nunca acepta un id del navegador. Un catalogo caido no tumba la
    vista: `trabajos.mis_solicitudes` lo marca en `listas_disponibles`."""
    usuario_id = await _usuario_de_sesion(authorization)
    return await trabajos.mis_solicitudes(api.app.state.motor, usuario_id, catalogo=api._catalogo())


@router.post(
    "/v1/trabajos/{trabajo_id}/ordenar",
    tags=["trabajos"],
    status_code=201,
    summary="Checkout: arma la orden del kit elegido y arranca el pago (server-to-server)",
)
async def ordenar_trabajo(
    trabajo_id: uuid.UUID,
    cuerpo: PeticionCheckout,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """El acudiente elige perfil + direccion; Inteligencia arma la orden en Comercio.

    El navegador no habla con Comercio: manda `trabajo_id` + perfil + correo +
    direccion, y aqui se resuelve el kit y se cobra. Devuelve la
    `url_redireccion` de la pasarela para mandar al acudiente a pagar. La sesion
    es opcional como al cambiar un producto: la ruta rapida admite trabajos sin
    cuenta, pero si el trabajo tiene dueno solo el lo paga.
    """
    portador = await _usuario_de_sesion(authorization) if token_bearer(authorization) else None
    try:
        return await trabajos.ordenar(
            api.app.state.motor,
            trabajo_id,
            portador=portador,
            perfil=cuerpo.perfil,
            # Sin los `None`: el checkout legado manda el mismo cuerpo de siempre.
            entrega=cuerpo.entrega.model_dump(exclude_none=True),
            correo=cuerpo.correo,
            metodo=cuerpo.metodo,
            url_redireccion=cuerpo.url_redireccion,
            comercio=api._comercio(),
            catalogo=api._catalogo(),
            identidad=api._identidad(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_ordenable",
            "Ese trabajo no tiene un kit de ese perfil para comprar.",
            estado=404,
        ) from error
    except trabajos.CambioNoPermitido as error:
        raise ErrorDominio(error.codigo, error.mensaje, estado=error.estado) from error
    except trabajos.CheckoutRechazado as error:
        # Comercio rechazo por negocio (p.ej. precio_cambiado): se reenvia su
        # cuerpo verbatim y su estado, para que el acudiente vea el motivo.
        raise ErrorDominio(
            str(error.cuerpo.get("error") or "checkout_rechazado"),
            str(error.cuerpo.get("mensaje") or "El pago no se pudo iniciar."),
            estado=error.estado,
        ) from error
    except trabajos.RemotoCaido as error:
        raise ErrorDominio(
            "servicio_no_disponible",
            f"No se pudo completar el checkout: {error.servicio} no respondio.",
            estado=503,
        ) from error


@router.post(
    "/v1/trabajos/{trabajo_id}/reintentar",
    tags=["trabajos"],
    summary="Vuelve a correr un trabajo fallido, sin repetir lo que ya estaba bien",
)
async def reintentar(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Existe porque un trabajo fallido con diagnostico es reintentable.

    Es la contraparte de la seccion 8: si Gemini o el catalogo no
    respondieron, el trabajo quedo guardado con su error y el acudiente no
    tiene que volver a subir nada.
    """
    try:
        actual = await trabajos.ver(api.app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error

    if actual["estado"] not in {EstadoTrabajo.FALLIDO.value, EstadoTrabajo.ENCOLADO.value}:
        raise ErrorDominio(
            "estado_incompatible",
            f"Solo se reintenta un trabajo fallido o encolado, y este esta en {actual['estado']}.",
            estado=409,
        )

    await trabajos.lanzar(api.app.state.motor, trabajo_id)
    return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.ENCOLADO.value}


# ---------------------------------------------------------------------------
# Onboarding de listas (apps/admin): un PDF entra, el catalogo recibe la lista
# ---------------------------------------------------------------------------


class ParteMultipart:
    """Una parte de un `multipart/form-data`: su nombre, si es archivo y bytes.

    Se conserva el ORDEN y la REPETICION de las partes (una subida de varios
    hijos manda varios `archivo`/`referencia` con el mismo nombre), cosa que el
    aplanado a diccionario de `_leer_multipart` pierde a proposito para el
    onboarding de un solo PDF.
    """

    __slots__ = ("nombre", "es_archivo", "contenido")

    def __init__(self, nombre: str, es_archivo: bool, contenido: bytes) -> None:
        self.nombre = nombre
        self.es_archivo = es_archivo
        self.contenido = contenido

    def texto(self) -> str:
        return self.contenido.decode("utf-8", "replace")


def _partes_multipart(cuerpo: bytes, tipo_contenido: str) -> list[ParteMultipart]:
    """Trocea un `multipart/form-data` en partes, en orden y con repeticiones.

    Se parsea a mano y no con `UploadFile`/`Form` de FastAPI a proposito: esos
    exigen `python-multipart` en el arranque y este servicio no lo trae. Un
    parseo por frontera alcanza para el punado de campos y archivos que suben
    el onboarding y la subida de listas, sin arrastrar una dependencia nueva.
    """
    marca = "boundary="
    posicion = tipo_contenido.find(marca)
    if posicion < 0:
        raise ErrorDominio("multipart_invalido", "El envio no es un formulario multipart valido.", estado=422)
    frontera = tipo_contenido[posicion + len(marca) :].strip().strip('"')
    separador = b"--" + frontera.encode()

    partes: list[ParteMultipart] = []
    for bruto in cuerpo.split(separador):
        bruto = bruto.strip(b"\r\n")
        if not bruto or bruto == b"--":
            continue
        cabeza, _, contenido = bruto.partition(b"\r\n\r\n")
        disposicion = ""
        for linea in cabeza.split(b"\r\n"):
            if linea.lower().startswith(b"content-disposition"):
                disposicion = linea.decode("latin-1", "replace")
        nombre = re.search(r'name="([^"]*)"', disposicion)
        if not nombre:
            continue
        partes.append(ParteMultipart(nombre.group(1), 'filename="' in disposicion, contenido))
    return partes


def _leer_multipart(cuerpo: bytes, tipo_contenido: str) -> tuple[dict[str, str], dict[str, bytes]]:
    """Separa campos de archivos de un `multipart/form-data`, aplanado a dict.

    Es la vista que le sirve al onboarding, que sube un solo PDF y un punado de
    campos de texto: la ultima parte de cada nombre gana. Para una subida con
    partes repetidas usa `_partes_multipart`, que conserva orden y repeticion.
    """
    campos: dict[str, str] = {}
    archivos: dict[str, bytes] = {}
    for parte in _partes_multipart(cuerpo, tipo_contenido):
        if parte.es_archivo:
            archivos[parte.nombre] = parte.contenido
        else:
            campos[parte.nombre] = parte.texto()
    return campos, archivos


def _items_desde_percepcion(percepcion: Percepcion) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """De una percepcion aceptada a `(items, percepcion_cruda)` para el catalogo.

    Un `descripcion` es el `texto_original` que el catalogo va a emparejar, una
    `cantidad` en null se vuelve 1, y la evidencia por pagina lleva el texto
    leido —`crudo` es una cadena (contrato: `PercepcionCruda`), no una lista de
    objetos: la region 2 la pinta directamente—. La percepcion ya viene agregada
    (sin items por pagina), asi que el texto leido se muestra en la pagina 1.
    """
    items = [
        {
            "texto_original": item.descripcion,
            "cantidad": item.cantidad or 1,
            "confianza": item.confianza,
        }
        for item in percepcion.items
    ]
    leido = "\n".join(
        f"{item.cantidad} {item.descripcion}".strip() if item.cantidad else item.descripcion
        for item in percepcion.items
    )
    percepcion_cruda = [
        {"pagina": numero, "crudo": leido if numero == 1 else ""}
        for numero in range(1, percepcion.paginas + 1)
    ]
    return items, percepcion_cruda


class ColegioElegido(BaseModel):
    """A que colegio va una lista subida, tal como lo designo quien la sube.

    La comparten la subida del acudiente (`HijoSubida`) y el onboarding del staff
    desde la cola: las dos puertas designan el colegio igual y derivan el mismo
    `colegio_id`. Se designa de UNA de tres formas:
      • `colegio_id`: un colegio que Tukit ya conoce (ruta "lista_oficial").
      • `colegio_dane` (+ `colegio_nombre`): elegido del directorio de Bogota; el
        colegio aun no existe en Tukit y nacera cuando un administrador apruebe.
        El id se deriva del DANE con el contrato compartido.
      • solo `colegio_nombre`: escrito a mano porque no estaba en el directorio;
        el id se deriva del nombre normalizado para que dos subidas del mismo
        colegio converjan a la misma version.
    """

    colegio_id: str | None = Field(default=None, max_length=64)
    colegio_dane: str | None = Field(default=None, max_length=32)
    colegio_nombre: str | None = Field(default=None, max_length=256)

    def resolver_colegio(self) -> tuple[str, dict[str, Any] | None]:
        """El `colegio_id` estable y, si el colegio aun no existe en Tukit, los
        datos con que la aprobacion creara su identidad.

        Un `colegio_id` explicito (aliado conocido) no trae datos: no hay
        identidad que crear. El directorio y el texto a mano SI los traen, para
        que la cola muestre el nombre y el poller de Identidad haga el upsert.
        """
        if self.colegio_id:
            return self.colegio_id, None
        nombre = (self.colegio_nombre or "").strip()
        if self.colegio_dane:
            colegio_id = str(derivar("colegio", self.colegio_dane))
            datos: dict[str, Any] = {"dane": self.colegio_dane, "nombre": nombre or None}
            return colegio_id, datos
        if nombre:
            # Nombre normalizado (espacios colapsados, minusculas) como llave, para
            # que "  Gimnasio  Del Norte " y "gimnasio del norte" sean el mismo.
            clave = " ".join(nombre.lower().split())
            colegio_id = str(derivar("colegio", "libre", clave))
            return colegio_id, {"dane": None, "nombre": " ".join(nombre.split())}
        raise ErrorDominio(
            "colegio_requerido",
            "Falta el colegio del hijo: elige uno o escribe su nombre.",
            estado=422,
            campo="colegio",
        )


class HijoSubida(ColegioElegido):
    """Un hijo de una subida de listas: a que (colegio, grado) va su PDF. El
    colegio se designa como en `ColegioElegido`."""

    referencia: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int | None = Field(default=None, ge=2020, le=2100)
    # Como llama el acudiente a este hijo: rotula su kit. NO viaja al Catalogo
    # (no guarda datos de menores): se queda cifrado en Inteligencia hasta que
    # el poller arma el kit (`apodos_subida`). Mismas reglas que en `/v1/trabajos`.
    apodo: str | None = Field(default=None, max_length=40)

    @field_validator("apodo", mode="before")
    @classmethod
    def _recortar_apodo(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v


def _nombre_comparable(nombre: str | None) -> str:
    """Minusculas, sin tildes y con espacios colapsados: "Colegio  ALAMEÍ" y
    "colegio alamei" son el mismo nombre."""
    sin_tildes = unicodedata.normalize("NFKD", nombre or "")
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


async def _reusar_colegio_conocido(
    colegio_id: str, colegio_datos: dict[str, Any] | None
) -> tuple[str, dict[str, Any] | None]:
    """Si el colegio "nuevo" ya existe en Identidad, su id y sin datos de alta.

    El buscador de /empezar solo ofrece como aliado a los colegios con un grado
    verificado; uno que existe sin listas hay que escribirlo "tal cual", y el id
    derivado del nombre (o del DANE) no es el suyo: aprobar daba de alta un
    duplicado (H-UG-01). Se pregunta a Identidad por su API, no por su base.
    Coincide el mismo DANE, o el mismo nombre comparable si el que existe no
    tiene DANE o tiene el mismo (dos homonimos con DANE distinto son dos
    colegios). Sin Identidad, queda el id derivado de siempre.
    """
    if colegio_datos is None:
        return colegio_id, colegio_datos
    dane = colegio_datos.get("dane")
    nombre = _nombre_comparable(colegio_datos.get("nombre"))
    conocidos = await api._identidad().colegios_conocidos()
    por_dane = [c for c in conocidos if dane and c.get("dane") == dane]
    por_nombre = [
        c
        for c in conocidos
        if nombre
        and _nombre_comparable(c.get("nombre")) == nombre
        and (not c.get("dane") or c.get("dane") == dane)
    ]
    for conocido in (*por_dane, *por_nombre):
        if conocido.get("colegio_id"):
            return str(conocido["colegio_id"]), None
    return colegio_id, colegio_datos


async def _completar_con_directorio(colegio_datos: dict[str, Any] | None) -> dict[str, Any] | None:
    """Colegio nuevo elegido del directorio: se pre-llena su perfil (direccion,
    contacto, sitio) con el DUEB para que la cola no muestre un bloque vacio.
    El nombre/dane de la subida mandan; el directorio solo tapa huecos. Sin DANE
    (escrito a mano) o con Identidad caida, quedan los datos tal cual."""
    if not (colegio_datos and colegio_datos.get("dane")):
        return colegio_datos
    del_dueb = await api._identidad().datos_directorio(colegio_datos["dane"])
    if not del_dueb:
        return colegio_datos
    return {**del_dueb, **{k: v for k, v in colegio_datos.items() if v}}


@router.post(
    "/v1/listas/subir",
    tags=["listas"],
    status_code=202,
    summary="§2: un acudiente sube el PDF de cada hijo; cada uno queda como version pendiente",
)
async def subir_listas(peticion: Request) -> dict[str, Any]:
    """La puerta del acudiente: PDFs entran, versiones PENDIENTES salen.

    A diferencia de `POST /v1/trabajos` (que arma un kit desechable) y de
    `POST /v1/admin/onboarding` (la subida de un administrador, un PDF por vez),
    esto percibe el PDF de CADA hijo y lo importa al catalogo como una version
    SIN revisar de esa (colegio, grado), ligada al padre por su
    `contacto_referencia` —el `usuario_id` que Identidad emite; nunca su correo
    ni telefono—. No se crea ningun trabajo: el padre espera a que un
    administrador apruebe la version, y recien ahi se arma su kit.

    La percepcion es todo o nada por hogar: si rechaza el archivo de un hijo
    (varios grados, pagina a medias, ilegible) no se guarda NADA y se responde
    422 con el codigo del rechazo, sin devolver jamas el contenido subido. Dos
    hijos del mismo (colegio, grado) comparten una sola version: se importa una
    vez para no pisar una lista con la otra.

    Si el catalogo no responde (ADR 0040), la subida responde igual 202: lo que
    no alcanzo a importarse queda guardado en `importacion_lista`, todo junto y
    con lo ya percibido, y su hijo trae `version_id: null, estado: "pendiente"`.
    El trabajador lo importa cuando el catalogo vuelve, con la misma clave de
    idempotencia y sin volver a percibir. Con el catalogo arriba, la respuesta
    es la de siempre y aqui no queda copia de la lista ni del PDF.
    """
    tipo = peticion.headers.get("content-type", "")
    if "multipart/form-data" not in tipo:
        raise ErrorDominio("multipart_invalido", "Sube las listas como multipart/form-data.", estado=422)

    # Si el acudiente ya viene autenticado, su usuario_id sale de la sesion y
    # ES la traza que baja al catalogo. Solo el flujo anonimo registra contacto.
    usuario_id = await api._usuario_de_la_peticion(peticion)

    partes = _partes_multipart(await peticion.body(), tipo)
    hijos_crudo = ""
    contacto_crudo = ""
    preferencias_crudo = ""
    # `archivo` y `referencia` llegan como partes repetidas y APAREADAS por
    # orden (cada `archivo` seguido de su `referencia`), igual que las escribe
    # `crearTrabajo`/el navegador. Se recogen en orden y se aparean por indice.
    archivos_orden: list[bytes] = []
    referencias_orden: list[str] = []
    for parte in partes:
        if parte.nombre == "hijos" and not parte.es_archivo:
            hijos_crudo = parte.texto()
        elif parte.nombre == "contacto" and not parte.es_archivo:
            contacto_crudo = parte.texto()
        elif parte.nombre == "preferencias" and not parte.es_archivo:
            preferencias_crudo = parte.texto()
        elif parte.nombre == "archivo" and parte.es_archivo:
            archivos_orden.append(parte.contenido)
        elif parte.nombre == "referencia" and not parte.es_archivo:
            referencias_orden.append(parte.texto())

    archivos: dict[str, bytes] = {}
    for indice, contenido in enumerate(archivos_orden):
        clave = referencias_orden[indice] if indice < len(referencias_orden) else str(indice)
        archivos[clave] = contenido

    try:
        hijos = [HijoSubida(**h) for h in json.loads(hijos_crudo or "[]")]
    except (ValueError, TypeError) as error:
        raise ErrorDominio(
            "hijos_invalidos",
            "El campo `hijos` no trae una lista de hijos valida.",
            estado=422,
            campo="hijos",
        ) from error
    if not hijos:
        raise ErrorDominio(
            "hijos_requeridos", "Sube al menos un hijo con su archivo.", estado=422, campo="hijos"
        )

    # El contacto es opcional: sin el, la lista igual se importa (perder el
    # aviso es malo, perder la lista por no poder avisar es peor).
    contacto = None
    if contacto_crudo:
        try:
            contacto = Contacto(**json.loads(contacto_crudo))
        except (ValueError, TypeError) as error:
            raise ErrorDominio(
                "contacto_invalido", "El contacto no es valido.", estado=422, campo="contacto"
            ) from error

    # Las preferencias del paso 3 son del HOGAR, no de un hijo: se guardan en
    # cada version importada para que, al aprobarla, el kit del padre se optimice
    # con lo que pidio (pesos, disposicion, personaje) y no con los por omision.
    # Son opcionales: sin ellas la aprobacion cae a los pesos por defecto.
    preferencias: dict[str, Any] | None = None
    if preferencias_crudo:
        try:
            crudo = json.loads(preferencias_crudo)
        except ValueError as error:
            raise ErrorDominio(
                "preferencias_invalidas",
                "Las preferencias no son un JSON valido.",
                estado=422,
                campo="preferencias",
            ) from error
        if not isinstance(crudo, dict):
            raise ErrorDominio(
                "preferencias_invalidas",
                "Las preferencias tienen que ser un objeto.",
                estado=422,
                campo="preferencias",
            )
        if crudo.get("personaje_por_hijo") is not None:
            try:
                _VALIDAR_PERSONAJE_POR_HIJO.validate_python(crudo["personaje_por_hijo"])
            except ValidationError as error:
                raise ErrorDominio(
                    "preferencias_invalidas",
                    "Los personajes por hijo no son validos.",
                    estado=422,
                    campo="preferencias.personaje_por_hijo",
                ) from error
        preferencias = crudo or None

    # Cada hijo tiene que traer su archivo, por referencia o por orden. Se exige
    # ANTES de tocar Identidad o el catalogo: nada a medias.
    def _archivo_de(indice: int, referencia: str) -> bytes:
        if referencia in archivos:
            return archivos[referencia]
        if str(indice) in archivos:
            return archivos[str(indice)]
        raise ErrorDominio(
            "archivo_faltante",
            "Falta el archivo de un hijo de la subida.",
            estado=422,
            campo="archivo",
        )

    pdf_por_hijo = [_archivo_de(i, h.referencia) for i, h in enumerate(hijos)]

    # Se percibe TODO antes de escribir NADA: si un archivo se rechaza, ni
    # Identidad ni el catalogo se tocan. La percepcion resuelve el grado real
    # del PDF (puede diferir del que el acudiente eligio) para deduplicar bien.
    percibidos: list[tuple[HijoSubida, str, bytes, Percepcion]] = []
    for hijo, pdf in zip(hijos, pdf_por_hijo, strict=True):
        percepcion = await api._percibir_onboarding(pdf)
        if not percepcion.aceptada:
            raise PercepcionRechazada(
                percepcion.error or "percepcion_rechazada",
                percepcion.mensaje,
                grados_detectados=percepcion.grados,
            )
        grado = percepcion.grados[0] if percepcion.grados else hijo.grado
        percibidos.append((hijo, grado, pdf, percepcion))

    # El contacto se registra UNA vez para el hogar, no una por hijo. Su id es
    # la unica traza que baja al catalogo. Si ya hay sesion, el usuario_id de la
    # sesion es esa traza y no se re-registra nada (refleja trabajos.crear:160).
    contacto_referencia: str | None = usuario_id
    if usuario_id is None and contacto and contacto.correo:
        contacto_referencia = await api._identidad().registrar_contacto(contacto.correo, contacto.celular)

    # Se importa una version por (colegio, grado): dos hijos del mismo destino
    # comparten la misma, para no pisar una lista con la otra. El `colegio_id` se
    # DERIVA (del aliado elegido, del DANE del directorio o del nombre a mano) y
    # con el viajan los datos del colegio cuando este aun no existe en Tukit,
    # para que la cola lo muestre y la aprobacion cree su identidad.
    por_destino: dict[tuple[str, int], importaciones.Destino] = {}
    destino_de_hijo: list[tuple[HijoSubida, str, tuple[str, int]]] = []
    anio_por_omision = 2026
    for hijo, grado, pdf, percepcion in percibidos:
        colegio_id, colegio_datos = await _reusar_colegio_conocido(*hijo.resolver_colegio())
        anio = hijo.anio_lectivo or anio_por_omision
        clave = (f"{colegio_id}|{grado}", anio)
        destino_de_hijo.append((hijo, grado, clave))
        if clave in por_destino:
            por_destino[clave].referencias.append(hijo.referencia)
            continue
        colegio_datos = await _completar_con_directorio(colegio_datos)
        items, percepcion_cruda = _items_desde_percepcion(percepcion)
        por_destino[clave] = importaciones.Destino(
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio,
            referencias=[hijo.referencia],
            items=items,
            percepcion_cruda=percepcion_cruda,
            documento=pdf,
            colegio_datos=colegio_datos,
        )

    # Cada destino viaja con su clave de idempotencia (ADR 0040). Un rechazo del
    # catalogo (un 4xx) sale como antes. Si el catalogo no responde, no se
    # insiste con el resto: cada intento puede costar la espera entera del
    # cliente. Ese destino y los que faltan quedan guardados con lo ya percibido,
    # y el trabajador los importa cuando el catalogo vuelva.
    catalogo = api._catalogo()
    subida_id = uuid.uuid4()
    versiones: dict[tuple[str, int], str] = {}
    caida: RemotoCaido | None = None
    for clave, destino in por_destino.items():
        try:
            respuesta = await catalogo.importar_lista(
                colegio_id=destino.colegio_id,
                grado=destino.grado,
                anio_lectivo=destino.anio_lectivo,
                items=destino.items,
                documento_base64=base64.b64encode(destino.documento).decode(),
                percepcion_cruda=destino.percepcion_cruda,
                contacto_referencia=contacto_referencia,
                preferencias=preferencias,
                colegio_datos=destino.colegio_datos,
                origen="sugerencia_padre",
                clave_idempotencia=str(importaciones.clave_de(subida_id, destino)),
                referencias=destino.referencias,
            )
        except RemotoCaido as error:
            if not error.transitorio:
                raise
            caida = error
            break
        versiones[clave] = str(respuesta["version_id"])
        await apodos_subida.guardar(
            api.app.state.motor,
            versiones[clave],
            contacto_referencia,
            {h.referencia: h.apodo for h, _, c in destino_de_hijo if c == clave and h.apodo},
        )

    if caida is not None:
        pendientes = [destino for clave, destino in por_destino.items() if clave not in versiones]
        for destino in pendientes:
            destino.apodos = {
                h.referencia: h.apodo
                for h, _, c in destino_de_hijo
                if h.apodo and por_destino.get(c) is destino
            }
        await importaciones.guardar(
            api.app.state.motor,
            subida_id,
            pendientes,
            caida=caida,
            contacto_referencia=contacto_referencia,
            preferencias=preferencias,
        )

    subidas: list[dict[str, Any]] = []
    for hijo, grado, clave in destino_de_hijo:
        if clave in versiones:
            subidas.append({"referencia": hijo.referencia, "version_id": versiones[clave], "grado": grado})
        else:
            subidas.append(
                {"referencia": hijo.referencia, "version_id": None, "grado": grado, "estado": "pendiente"}
            )

    return {"subidas": subidas, "contacto_referencia": contacto_referencia}


@router.post(
    "/v1/admin/onboarding",
    tags=["admin"],
    summary="Sube el PDF de una lista, lo percibe y lo importa al catalogo",
)
async def onboarding(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """De un PDF a una lista en el catalogo, pasando por la percepcion.

    Solo staff (`_exigir_staff`: 401 sin sesion, 403 sin rol, 503 si Identidad
    no responde), y antes de leer el formulario: quien no puede subir no gasta
    una lectura del PDF.

    El colegio se designa como en la subida del acudiente (`ColegioElegido`):
    `colegio_id` de uno que Tukit conoce, `colegio_dane` + `colegio_nombre` del
    directorio de Bogota, o solo `colegio_nombre` escrito a mano. En los dos
    ultimos el colegio aun no existe: sus datos viajan al catalogo
    (`colegio_datos`) para que la cola muestre su nombre y la aprobacion lo cree
    en Identidad. Sin `colegio_id` no hay acudiente esperando: el contacto va
    vacio y el origen sigue siendo `onboarding`.

    La percepcion es la unica puerta: si rechaza el archivo (varios grados,
    pagina a medias, ilegible) no se importa nada y se responde 422 con el
    codigo del rechazo. Nunca se le devuelve al cliente el contenido que
    subio, ni siquiera cuando se rechaza. Lo que si viaja al catalogo, cuando
    se acepta, es el PDF en base64 y la percepcion cruda por pagina, para que
    la revision humana del catalogo pueda contrastar.
    """
    await _exigir_staff(authorization)
    tipo = peticion.headers.get("content-type", "")
    if "multipart/form-data" not in tipo:
        raise ErrorDominio("multipart_invalido", "Sube la lista como multipart/form-data.", estado=422)
    campos, archivos = _leer_multipart(await peticion.body(), tipo)

    for requerido in ("grado", "anio_lectivo"):
        if requerido not in campos:
            raise ErrorDominio(
                "campo_faltante", "Falta un campo del formulario de onboarding.", estado=422, campo=requerido
            )
    try:
        elegido = ColegioElegido(
            colegio_id=campos.get("colegio_id") or None,
            colegio_dane=campos.get("colegio_dane") or None,
            colegio_nombre=campos.get("colegio_nombre") or None,
        )
    except ValidationError as error:
        raise ErrorDominio(
            "colegio_invalido", "El colegio de la lista no es válido.", estado=422, campo="colegio"
        ) from error
    # Antes de percibir: sin colegio no se gasta una lectura del PDF.
    colegio_id, colegio_datos = elegido.resolver_colegio()
    archivo = archivos.get("archivo")
    if archivo is None:
        raise ErrorDominio(
            "archivo_faltante", "No llego ningun archivo en el campo `archivo`.", estado=422, campo="archivo"
        )
    try:
        anio_lectivo = int(campos["anio_lectivo"])
    except ValueError as error:
        raise ErrorDominio(
            "anio_invalido", "El anio lectivo tiene que ser un numero.", estado=422, campo="anio_lectivo"
        ) from error

    percepcion = await api._percibir_onboarding(archivo)
    if not percepcion.aceptada:
        raise PercepcionRechazada(
            percepcion.error or "percepcion_rechazada",
            percepcion.mensaje,
            grados_detectados=percepcion.grados,
        )

    # Mismo mapeo (renglones + evidencia por pagina) que la subida del acudiente.
    items, percepcion_cruda = _items_desde_percepcion(percepcion)

    colegio_id, colegio_datos = await _reusar_colegio_conocido(colegio_id, colegio_datos)
    colegio_datos = await _completar_con_directorio(colegio_datos)
    # El grado lo pone la lectura, salvo que el admin lo confirme: el admin conoce el
    # esquema del colegio ("2do Año" es Octavo en Madre Matilde) y el modelo a veces
    # solo lee "Segundo". Lo leido queda en la evidencia por pagina para la revision.
    leido = percepcion.grados[0] if percepcion.grados else campos["grado"]
    grado = campos["grado"] if campos.get("grado_confirmado") == "1" else leido
    # A diferencia de la subida del acudiente, aqui no se difiere (ADR 0040):
    # el formulario del administrador necesita el `version_id` en el acto para
    # pasar a la curaduria, y el administrador puede volver a intentar.
    try:
        respuesta = await api._catalogo().importar_lista(
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
            items=items,
            documento_base64=base64.b64encode(archivo).decode(),
            percepcion_cruda=percepcion_cruda,
            colegio_datos=colegio_datos,
        )
    except RemotoCaido as error:
        if not error.transitorio:
            raise
        raise ErrorDominio(
            "servicio_no_disponible",
            "El catalogo no responde; la lista no se guardo. Intenta de nuevo en un momento.",
            estado=503,
        ) from error
    return {
        "version_id": respuesta["version_id"],
        "grado": grado,
        "items": len(items),
    }


class PeticionPreview(BaseModel):
    colegio_id: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int = Field(ge=2020, le=2100)


@router.post(
    "/v1/admin/onboarding/{version_id}/preview",
    tags=["admin"],
    summary="Arma los tres kits de una lista recien subida, ANTES de aprobarla",
)
async def preview_onboarding(version_id: str, peticion: PeticionPreview) -> dict[str, Any]:
    """Los tres kits + recomendacion de una version vigente pero SIN revisar.

    El admin acaba de subir un PDF (`POST /v1/admin/onboarding`) y quiere ver
    como quedan Ahorrador/Fan/Premium antes de aprobar la version. Se crea un
    trabajo DESECHABLE con `origen='preview_onboarding'` sobre ese
    (colegio, grado, anio): como la version es vigente pero sin revisar, el
    pipeline toma la ruta LENTA (emparejar + NSGA-II), que es exactamente la
    previsualizacion. No se autopublica: el trabajo se queda en
    `espera_revision`/`fallido` y solo sirve para pintar los kits.

    Se corre de forma SINCRONICA (no `trabajos.lanzar`) para que los kits ya
    esten escritos cuando el admin lea `GET /v1/admin/trabajos/{id}`.

    Se previsualiza la version del PATH, no la vigente: al Editar, el borrador
    nace sin vigencia (el acudiente sigue viendo la aprobada), asi que exigir que
    fuera la vigente rompia justo el caso de editar-y-previsualizar. La guarda
    solo comprueba que la version EXISTE y es la de ese (colegio, grado): 404 si
    no. El pipeline lee sus items por `version_id` (ver `_listas_por_hijo`).
    """
    catalogo = api._catalogo()
    try:
        cabeza = await catalogo.revision(version_id)
    except trabajos.RemotoCaido as error:
        raise ErrorDominio(
            "version_no_existe",
            "No hay ninguna version con ese identificador.",
            estado=404,
        ) from error
    # La version tiene que ser la del (colegio, grado, anio) que se pidio
    # previsualizar: un version_id de otra lista no se previsualiza aqui.
    if (
        str(cabeza.get("colegio_id") or "") != peticion.colegio_id
        or str(cabeza.get("grado") or "") != peticion.grado
        or int(cabeza.get("anio_lectivo") or 0) != peticion.anio_lectivo
    ):
        raise ErrorDominio(
            "version_no_corresponde",
            "Esa version no es de ese colegio, grado y anio.",
            estado=409,
        )

    # Previsualizar es idempotente por version: si el admin ya previsualizo
    # este (colegio, grado, anio), su preview anterior se descarta antes de
    # armar el nuevo. Sin esto, cada clic dejaba un trabajo desechable mas en
    # la cola y no habia forma de limpiarlos.
    for viejo in await trabajos.previews_de(
        api.app.state.motor, peticion.colegio_id, peticion.grado, peticion.anio_lectivo
    ):
        await trabajos.eliminar(api.app.state.motor, viejo)

    respuesta = await trabajos.crear(
        api.app.state.motor,
        hijos=[
            {
                "referencia": "preview",
                "colegio_id": peticion.colegio_id,
                "grado": peticion.grado,
                "anio_lectivo": peticion.anio_lectivo,
                # La version de la que salio el preview: si el admin lo fija como
                # canonico, el poller de `lista_aprobada` sabe que esa version ya
                # tiene sus kits y no vuelve a optimizar.
                "version_id": version_id,
            }
        ],
        contacto=None,
        preferencias={},
        origen="preview_onboarding",
        # Se procesa aqui mismo: que el trabajador no lo reclame a la vez.
        en_proceso=True,
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(api.app.state.motor, trabajo_id, catalogo=catalogo)
    return {"trabajo_id": str(trabajo_id), "estado": estado}


# ---------------------------------------------------------------------------
# Revision humana (apps/admin)
# ---------------------------------------------------------------------------


@router.get("/v1/admin/cola", tags=["admin"], summary="AD-02, AD-03: trabajos esperando a una persona")
async def cola(
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await trabajos.cola(api.app.state.motor, pagina=pagina, por_pagina=por_pagina)


@router.get(
    "/v1/admin/colegios/{colegio_id}/acudientes",
    tags=["admin"],
    summary="Los acudientes de un colegio con el estado de su trabajo mas reciente",
)
async def acudientes_de_colegio(colegio_id: str) -> dict[str, Any]:
    """Agrupado por usuario_id, el trabajo vivo de cada acudiente.

    Sin correo ni apodos de menores (Ley 1581 / Anexo M): esta superficie solo
    expone el identificador del acudiente, el estado y la fecha. El colegio se
    filtra dentro del JSON `hijos`, que es donde vive.
    """
    acudientes = await trabajos.acudientes_de_colegio(api.app.state.motor, colegio_id=colegio_id)
    return {"acudientes": acudientes}


@router.get(
    "/v1/admin/trabajos/{trabajo_id}",
    tags=["admin"],
    summary="AD-03: el trabajo CON sus kits, aunque todavia no este publicado",
)
async def ver_admin(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Mismo lector que el del acudiente, con los kits forzados.

    El acudiente no ve un kit sin revisar; Admin tiene que verlo, porque su
    trabajo es justamente revisarlo. Es la misma consulta con una bandera, y
    no dos lectores distintos que se puedan desincronizar.
    """
    try:
        return await trabajos.ver(
            api.app.state.motor, trabajo_id, incluir_kits=True, incluir_admin=True, catalogo=api._catalogo()
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@router.delete(
    "/v1/admin/trabajos/{trabajo_id}",
    tags=["admin"],
    status_code=204,
    summary="Borra un trabajo desechable (preview, encolado, fallido). No borra publicados.",
)
async def eliminar_trabajo(trabajo_id: uuid.UUID) -> None:
    """Borra un trabajo y su cascada. Un `publicado` esta protegido (409).

    Existe para limpiar los previews que se acumulan al previsualizar una lista
    varias veces, y cualquier trabajo desechable que ensucie la cola. La cascada
    de FKs se lleva etapas, items, kits y lineas; solo queda la bandeja de
    eventos, que es el log.
    """
    try:
        await trabajos.eliminar(api.app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.TrabajoProtegido as error:
        raise ErrorDominio(
            "trabajo_publicado_protegido",
            "Un trabajo publicado es el kit canonico de su colegio y grado; no se borra.",
            estado=409,
        ) from error


@router.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar",
    tags=["admin"],
    summary="AD-04: una persona da por bueno el emparejamiento",
)
async def validar_linea(trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea) -> dict[str, Any]:
    """Sin `sku` confirma el producto que la linea tiene en el kit.

    El catalogo va inyectado porque el producto validado puede no ser
    candidato del item (personaje del Fan, producto fijado por kit) y hay que
    registrarlo; si no hay producto por ningun lado, es un 422 con `campo`.
    """
    try:
        return await trabajos.decidir_linea(
            api.app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.RESUELTO_AUTO.value,
            sku=decision.sku,
            actor=decision.actor,
            motivo=decision.motivo,
            catalogo=api._catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error
    except trabajos.SinProductoQueValidar as error:
        mensaje = (
            f"El producto {error.sku} no esta en el catalogo: elige otro o marca la linea sin coincidencia."
            if error.sku
            else "Esta linea no tiene producto que validar: elige una alternativa, da de alta un producto "
            "o marcala sin coincidencia."
        )
        raise ErrorDominio("sin_producto_que_validar", mensaje, estado=422, campo="sku") from error
    except trabajos.KitsPublicadosNoEditables as error:
        raise ErrorDominio(
            "kits_publicados",
            "Estos kits ya estan publicados y no se editan en sitio. Usa «Editar kits» en la "
            "pagina del colegio: abre una version nueva y la vigente no cambia hasta publicarla.",
            estado=409,
        ) from error


@router.put(
    "/v1/admin/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item_id}/producto",
    tags=["admin"],
    summary="AD-04: fija el producto de UN kit (por-nivel), recalculando su subtotal",
)
async def fijar_producto(
    trabajo_id: uuid.UUID, perfil: str, item_id: uuid.UUID, cuerpo: ProductoEnLinea
) -> dict[str, Any]:
    """Escribe LINEA (no RESOLUCION): la eleccion de producto es por kit.

    A diferencia de `validar_linea` —que confirma el emparejamiento del item en
    los tres kits— esto cambia el producto de UN nivel. Es lo que hace que un
    concepto suba de economico a premium entre kits y que un personaje del Fan
    llegue de verdad al kit publicado.
    """
    try:
        # `todos`: el revisor resolvio el RENGLON (un hueco, un «consiguelo por
        # tu cuenta»), no un nivel: vale para cada kit del trabajo.
        if perfil == "todos":
            return await trabajos.fijar_producto_en_todos_los_kits(
                api.app.state.motor, trabajo_id, item_id, cuerpo.sku, catalogo=api._catalogo()
            )
        return await trabajos.fijar_producto_en_linea(
            api.app.state.motor, trabajo_id, perfil, item_id, cuerpo.sku, catalogo=api._catalogo()
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "linea_no_existe", "Ese trabajo no tiene esa linea en ese kit.", estado=404
        ) from error
    except trabajos.KitsPublicadosNoEditables as error:
        raise ErrorDominio(
            "kits_publicados",
            "Estos kits ya estan publicados y no se editan en sitio. Usa «Editar kits» en la "
            "pagina del colegio: abre una version nueva y la vigente no cambia hasta publicarla.",
            estado=409,
        ) from error


@router.get(
    "/v1/grados-canonicos",
    tags=["trabajos"],
    summary="Los (colegio, grado, anio) con cache bendita, para el selector de /empezar",
)
async def listar_grados_canonicos(
    colegio_id: Annotated[str | None, Query(description="Filtra a un colegio")] = None,
) -> dict[str, Any]:
    grados = await trabajos.grados_canonicos(api.app.state.motor, colegio_id=colegio_id)
    return {"grados": grados}


@router.post(
    "/v1/trabajos/aplicar-canonico",
    tags=["trabajos"],
    status_code=201,
    summary="Ruta rapida: aplica nivel + personaje a la cache bendita y solicita el pedido",
)
async def aplicar_canonico(cuerpo: AplicarCanonico, solicitud: Request) -> dict[str, Any]:
    """Sin re-optimizar y sin cola: crea el trabajo del acudiente y su pedido.

    Es la contraparte de subir un PDF (que si entra al pipeline). Un grado con
    cache bendita se resuelve al vuelo; el pedido congelado queda para Comercio.
    """
    # La sesion manda: si el acudiente viene autenticado, su usuario_id sale del
    # token y no del cuerpo (que el navegador ya no envia). El body queda como
    # respaldo del flujo server-to-server.
    if cuerpo.marcas_excluidas or cuerpo.solo_disponibles:
        raise ErrorDominio(
            "filtros_requieren_recalculo",
            "Con marcas excluidas o solo disponibles el kit se recalcula: crea un trabajo normal.",
            estado=422,
        )
    desde_token = await api._usuario_de_la_peticion(solicitud)
    usuario_id = uuid.UUID(desde_token) if desde_token else cuerpo.usuario_id
    try:
        return await trabajos.aplicar_canonico(
            api.app.state.motor,
            colegio_id=cuerpo.colegio_id,
            grado=cuerpo.grado,
            anio_lectivo=cuerpo.anio_lectivo,
            perfil=cuerpo.perfil,
            personaje=cuerpo.personaje,
            apodo=cuerpo.apodo,
            usuario_id=usuario_id,
            catalogo=api._catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "cache_no_existe",
            "Ese colegio y grado no tiene todavia un kit publicado; sube la lista.",
            estado=404,
        ) from error


@router.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/sin-coincidencia",
    tags=["admin"],
    summary="AD-04: una persona declara que el catalogo no lo tiene",
)
async def sin_coincidencia(
    trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea
) -> dict[str, Any]:
    """Marca `HUECO_CATALOGO` y no `SIN_MATCH`, y la diferencia importa.

    Si una persona miro la linea, entendio que pedia y concluyo que no lo
    tenemos, eso es un hueco de catalogo: "te entendi y no lo tengo".
    `SIN_MATCH` significa "no te entendi", y despues de una revision humana
    esa ya no es la verdad. Solo el primero se puede responder con una
    alternativa o con una disculpa util, y solo el primero alimenta la
    metrica de que le falta al catalogo.
    """
    try:
        return await trabajos.decidir_linea(
            api.app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.HUECO_CATALOGO.value,
            actor=decision.actor,
            motivo=decision.motivo,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error
    except trabajos.KitsPublicadosNoEditables as error:
        raise ErrorDominio(
            "kits_publicados",
            "Estos kits ya estan publicados y no se editan en sitio. Usa «Editar kits» en la "
            "pagina del colegio: abre una version nueva y la vigente no cambia hasta publicarla.",
            estado=409,
        ) from error


@router.post(
    "/v1/admin/trabajos/{trabajo_id}/revision",
    tags=["admin"],
    summary="AD-06: aprobar publica al acudiente, devolver reabre sin avisar",
)
async def revisar(trabajo_id: uuid.UUID, decision: DecisionRevision) -> dict[str, Any]:
    try:
        resultado = await trabajos.revisar(
            api.app.state.motor,
            trabajo_id,
            decision=decision.decision,
            nota=decision.nota,
            actor=decision.actor,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.TransicionIlegal as error:
        raise ErrorDominio(
            "estado_incompatible",
            f"Un trabajo en {error.actual} no se puede pasar a {error.pedida}.",
            estado=409,
        ) from error
    except trabajos.PreviewNoPublicable as error:
        raise ErrorDominio(
            "preview_no_publicable",
            "Este es un preview de la lista, no tiene acudiente a quien avisar. "
            "Para publicar, aprueba la lista en su revisión (crea el colegio y arma "
            "el trabajo del padre).",
            estado=409,
        ) from error
    except trabajos.CheckoutRechazado as error:
        # Aprobar un kit sin lineas comprables se niega con su motivo: fijar el
        # canonico solo garantizaria el 404 del acudiente al comprar.
        raise ErrorDominio(
            str(error.cuerpo.get("error") or "kit_no_aprobable"),
            str(error.cuerpo.get("mensaje") or "El trabajo no se puede aprobar."),
            estado=error.estado,
        ) from error

    if decision.decision == "devolver":
        await trabajos.lanzar(api.app.state.motor, trabajo_id)
    return resultado


@router.post(
    "/v1/admin/trabajos/{trabajo_id}/canonico",
    tags=["admin"],
    summary="Fija un preview como los kits canonicos de su grado (sin avisar a nadie)",
)
async def fijar_canonico(trabajo_id: uuid.UUID, cuerpo: FijarCanonico) -> dict[str, Any]:
    """La contraparte de "publicar" para un trabajo sin acudiente.

    El admin previsualizo los kits de una lista, quiza los ajusto, y aprueba:
    esos kits pasan a ser la cache canonica del (colegio, grado, anio) y el
    proximo acudiente sin tope de gasto los recibe por la ruta rapida, sin
    volver a correr el optimizador. Aprobar la LISTA es otra llamada (Catalogo);
    la consola del admin hace las dos.
    """
    try:
        return await trabajos.fijar_como_canonico(
            api.app.state.motor, trabajo_id, nota=cuerpo.nota, actor=cuerpo.actor
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.NoCanonizable as error:
        raise ErrorDominio(
            "trabajo_con_acudiente",
            "Solo un preview se guarda como kit canonico; el trabajo de un acudiente se publica.",
            estado=409,
        ) from error
    except trabajos.TransicionIlegal as error:
        raise ErrorDominio(
            "estado_incompatible",
            f"Un trabajo en {error.actual} no se puede guardar como canonico.",
            estado=409,
        ) from error
    except trabajos.BorradorDesactualizado as error:
        raise ErrorDominio(
            "borrador_desactualizado",
            "Mientras editabas, los kits de este grado se volvieron a publicar. "
            "Descarta este borrador y abre uno nuevo desde la version vigente.",
            estado=409,
        ) from error


@router.post(
    "/v1/admin/trabajos/{trabajo_id}/borrador",
    tags=["admin"],
    summary="Abre una copia editable de los kits canonicos vigentes (nueva version)",
)
async def abrir_borrador(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Editar kits ya publicados es preparar su version siguiente.

    Copia el canonico a un trabajo en revision que la consola corrige; al
    guardarlo como canonico (`POST .../canonico`) pasa a ser el vigente y el
    anterior queda para los acudientes que ya lo tenian. Si ya hay un borrador
    abierto de ese canonico, devuelve ese.
    """
    try:
        return await trabajos.abrir_borrador(api.app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.BorradorDesactualizado as error:
        raise ErrorDominio(
            "canonico_no_vigente",
            "Estos kits ya no son los vigentes de su grado; edita la version actual.",
            estado=409,
        ) from error


@router.get(
    "/v1/metricas/colegios/{colegio_id}",
    tags=["metricas"],
    summary="Metricas en vivo de un colegio: kits armados, cobertura y ahorro.",
)
async def metricas_colegio(colegio_id: str) -> dict[str, Any]:
    """El panel del colegio, calculado sobre los trabajos publicados.

    Cuenta los kits recomendados publicados para el colegio, la cobertura del
    catalogo sobre sus lineas comprables (FU-06 medida, no prometida) y el
    ahorro que la consolidacion entre hermanos imputo. Un colegio sin trabajos
    publicados responde con ceros, no con 404: la ausencia de kits es una
    respuesta valida y el panel la sabe pintar.

    El colegio no es una columna de este servicio: vive en el JSON `hijos` de
    cada trabajo, tal como lo mando el acudiente. Por eso el filtro se hace en
    memoria sobre lo publicado; ver `metricas.py`.

    La ruta cuelga de `/v1/metricas/` y no de `/v1/colegios/` a proposito:
    `/v1/colegios` es superficie de Identidad (el catalogo institucional) y el
    gateway rutea por prefijo. Colgarla ahi la mandaria a Identidad; bajo
    `/v1/metricas` llega a Inteligencia, que es quien tiene los kits.
    """
    return await metricas.metricas_de_colegio(api.app.state.motor, colegio_id)


@router.get(
    "/v1/metricas/colegios/{colegio_id}/pedidos",
    tags=["metricas"],
    summary="Padres y ninos con pedido pagado en un colegio, por grado. Solo staff.",
)
async def metricas_pedidos_colegio(
    colegio_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """El cruce `pedido pagado -> trabajo -> hijos -> padre` del colegio.

    Exige Bearer de operador/admin (misma semantica que `/v1/admin/acudientes`):
    la respuesta lista los `usuario_id` de los padres que pagaron en el colegio,
    que es dato sensible aunque no sea correo. El correo lo resuelve aparte el
    servidor del admin con el endpoint protegido de acudientes.

    Comercio devuelve por HTTP (`GET /v1/comercio/pedidos-pagados`) los pedidos
    en estado confirmado con su `{trabajo_id, usuario_id}`; aqui se cruzan con
    los `hijos` del trabajo (que si tienen colegio y grado) y se agrega. Un
    colegio sin pedidos pagados responde con ceros y listas vacias, no con 404.

    Cuelga de `/v1/metricas/` por la misma razon que `metricas_colegio`: el
    gateway rutea por prefijo y este es el servicio dueno del cruce (ya habla con
    Comercio para el checkout).
    """
    await _exigir_staff(authorization)
    return await metricas.resumen_pedidos_de_colegio(api.app.state.motor, colegio_id, api._comercio())
