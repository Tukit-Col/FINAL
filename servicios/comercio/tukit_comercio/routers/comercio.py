"""Las rutas de Comercio: parsear, llamar al dominio, delegar al repo.

Dos superficies, como en el §9 del contrato:

- **Lectura** (`GET /v1/comercio/pedidos`, `/mis-pedidos`, `/{id}`): el tablero
  del back-office de logística y el historial del acudiente. El tablero y el
  detalle son SOLO para staff (operador/admin); "mis pedidos" exige sesión y usa
  el usuario DE LA SESIÓN. Ambas puertas validan el Bearer contra Identidad y
  fallan cerradas (503) si no responde.
- **Escritura** (`POST /v1/ordenes`, `/{id}/pago`, `/v1/webhooks/wompi`,
  `/{id}/retracto`): el checkout. Tres invariantes que no se negocian:
  re-verificar precio antes de cobrar (`422 precio_cambiado`); precio CONGELADO
  en la línea y dirección CONGELADA en el envío (ADR 0012 / 0015); no se guarda
  medio de pago, sólo id de transacción y estado (SG-03). El webhook es
  idempotente contra `evento_pasarela_procesado`.

El router no calcula ni arma SQL: `reverificar_precios`/`total_orden`/
`pedido_tras_pago` viven en `dominio/`, y todo el SQL en `repositorios/`. Aquí
sólo se orquesta y se traducen los resultados a sobres de error.

Los singletons (`pasarela`, `catalogo`, `identidad`, `motor`) se leen de `request.app.state`
en cada petición, no se capturan al importar: así las pruebas pueden sustituir
los dobles después de construir la app.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Header, Request
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.exc import IntegrityError
from tukit_comun.http import ErrorDominio
from tukit_comun.metricas import contar_orden_creada, contar_pago_aprobado

from ..dominio.despacho import preparar_avance, validar_avance
from ..dominio.linea_de_tiempo import linea_de_tiempo
from ..dominio.ordenes import LineaResuelta, reverificar_precios, total_orden
from ..dominio.pagos import CAMPOS_FIRMA_ENTREGA, firma_orden, vencido
from ..dominio.retracto import evaluar_retracto, pasos_del_pedido
from ..modelos import EstadoPago, EstadoPedido, MetodoPago, transicion_valida
from ..pasarela import EventoPasarela, PasarelaCaida, TransaccionNoExiste
from ..remoto import CatalogoCaido, IdentidadCaida
from ..repositorios import RepoPedidos
from ..repositorios.pedidos import ResultadoAplicacion

router = APIRouter(tags=["comercio"])


def _repo(conexion: Any) -> RepoPedidos:
    return RepoPedidos(conexion)


# ---------------------------------------------------------------------------
# Sesion: quien llama. Mismas puertas y mismos sobres que inteligencia
# (`_exigir_staff` / `_usuario_de_sesion`), para que el front trate igual un 401
# de cualquier servicio.
# ---------------------------------------------------------------------------

# Los roles del equipo interno; el admin es superconjunto del operador.
_ROLES_STAFF = frozenset({"admin", "operador"})


def _token_bearer(authorization: str | None) -> str | None:
    """El token del encabezado `Authorization`: `Bearer <token>` o el token pelado."""
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


async def _sesion_valida(request: Request, authorization: str | None) -> dict[str, Any]:
    """La sesion del portador, validada contra Identidad por HTTP (Comercio no
    lee la base de Identidad: regla 1). 401 sin token o con uno invalido; 503 si
    Identidad no responde: FALLA CERRADA, no autorizar por no poder preguntar."""
    token = _token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    try:
        sesion = await request.app.state.identidad.sesion(token)
    except IdentidadCaida as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    return sesion


@dataclass(frozen=True)
class Actor:
    """Quien del equipo interno hace la peticion: lo que queda en el historial."""

    usuario_id: uuid.UUID
    correo: str | None


async def _exigir_staff(request: Request, authorization: str | None) -> Actor:
    """Puerta operador/admin: 401/503 como `_sesion_valida`, 403 si el rol no es
    staff. Devuelve el actor (id y correo de la sesion), que queda en el historial."""
    sesion = await _sesion_valida(request, authorization)
    roles = {r.get("rol") for r in sesion.get("roles", [])}
    if not roles & _ROLES_STAFF:
        raise ErrorDominio(
            "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.", estado=403
        )
    return Actor(usuario_id=uuid.UUID(str(sesion["usuario_id"])), correo=sesion.get("correo"))


async def _usuario_de_sesion(request: Request, authorization: str | None) -> uuid.UUID:
    """Puerta de portador: cualquier sesion valida, sin rol. Devuelve el
    `usuario_id` DE LA SESION, nunca uno que venga del navegador."""
    sesion = await _sesion_valida(request, authorization)
    return uuid.UUID(str(sesion["usuario_id"]))


async def _pedido_o_404(repo: RepoPedidos, pedido_id: uuid.UUID) -> Any:
    fila = await repo.obtener(pedido_id)
    if fila is None:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
    return fila


# ---------------------------------------------------------------------------
# Lectura: tablero de logística e historial del acudiente
# ---------------------------------------------------------------------------


@router.get("/v1/comercio/pedidos", summary="Tablero de logistica: resumen + pedidos")
async def tablero(request: Request, authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Todos los pedidos con la direccion de quien recibe: solo staff. Sin el
    celular del repartidor (eso solo en el detalle)."""
    await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        resumen = await repo.resumen()
        pedidos = await repo.pedidos_completos(await repo.listar_todos())
    return {"resumen": resumen, "pedidos": pedidos}


@router.get("/v1/comercio/mis-pedidos", summary="El historial de pedidos de un acudiente, para su panel.")
async def mis_pedidos(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """Los pedidos del PORTADOR del token, mas recientes primero, para el
    dashboard del padre.

    El `usuario_id` sale de la sesion validada contra Identidad por HTTP, no del
    navegador: antes se aceptaba `?usuario_id=` y cualquiera podia leer los
    pedidos de otro. Si alguien lo sigue mandando, se ignora.
    """
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedidos = await repo.pedidos_completos(await repo.listar_de_usuario(usuario_id))
        pedidos = [await _con_seguimiento(repo, p) for p in pedidos]
    return {"total": len(pedidos), "pedidos": pedidos}


def _ahora() -> datetime:
    """El reloj del retracto; las pruebas lo sustituyen."""
    return datetime.now(UTC)


def _fecha(valor: Any) -> datetime | None:
    """Una fecha ISO del serializador (o ya datetime) como `datetime`, o `None`."""
    if valor is None or isinstance(valor, datetime):
        return valor
    return datetime.fromisoformat(str(valor))


async def _con_seguimiento(repo: RepoPedidos, pedido: dict[str, Any]) -> dict[str, Any]:
    """Un pedido del acudiente con su linea de tiempo y lo que puede hacer con el retracto.

    Del historial interno solo salen el estado y la hora (nunca el actor, la nota
    ni la incidencia). El plazo del retracto (Ley 1480, art. 47) corre desde la
    entrega; la regla vive en `dominio/retracto`.
    """
    pedido_id = uuid.UUID(pedido["pedido_id"])
    historial = await repo.historial_de(pedido_id)
    pago_en = await repo.pago_aprobado_en(pedido_id)
    devolucion = await repo.devolucion_de(pedido_id)
    envio = pedido.get("envio") or {}
    entregado_en = _fecha(envio.get("entregado_en"))
    pasos = pasos_del_pedido(
        creado_en=_fecha(pedido["creado_en"]),  # type: ignore[arg-type]
        pago_aprobado_en=_fecha(pago_en),
        historial=[{**h, "creado_en": _fecha(h["creado_en"])} for h in historial],
        entregado_en=entregado_en,
    )
    estado = evaluar_retracto(
        pedido["estado"], entregado_en, _ahora(), ya_solicitado=devolucion is not None
    )
    # El historial interno y el celular del repartidor no son del acudiente.
    envio_publico = {k: v for k, v in envio.items() if k != "repartidor_celular"} or None
    return {
        **pedido,
        "envio": envio_publico,
        "seguimiento": [{**p, "en": _iso_o_none(p["en"])} for p in pasos],
        "retracto": {
            "puede": estado.puede,
            "razon": estado.razon,
            "vence_en": _iso_o_none(estado.vence_en),
            "antes_de_entrega": estado.antes_de_entrega,
            "solicitado_en": _iso_o_none(devolucion.creado_en) if devolucion is not None else None,
        },
    }


def _iso_o_none(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.isoformat()


@router.get(
    "/v1/comercio/pedidos-pagados",
    summary="Los pedidos pagados (estado confirmado) con su trabajo, para cruces internos.",
)
async def pedidos_pagados(request: Request) -> dict[str, Any]:
    """El minimo cruce que otro servicio necesita: por cada pedido en un estado
    confirmado y con `trabajo_id`, su `{trabajo_id, usuario_id, estado}`. Nada de
    PII (solo identificadores) y la definicion de "pagado" queda aqui, en
    Comercio, que es su dueno.

    Lo consume Inteligencia server-to-server para armar las metricas de pedidos
    por colegio; el navegador nunca lo llama. Va sin token: la puerta la
    responde como ruta inexistente (`RUTAS_BLOQUEADAS` del gateway)."""
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        filas = await repo.pagados_con_trabajo()
    return {
        "pedidos": [
            {"trabajo_id": str(f.trabajo_id), "usuario_id": str(f.usuario_id), "estado": f.estado}
            for f in filas
        ]
    }


@router.get("/v1/comercio/pedidos/{pedido_id}", summary="Un pedido, con lineas, pago y envio")
async def ver_pedido(
    request: Request, pedido_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """El detalle del back-office: solo staff. Es la unica lectura que trae el
    celular del repartidor (para llamarlo) y el historial de avances."""
    await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        return await _detalle_staff(repo, await _pedido_o_404(repo, pedido_id))


async def _detalle_staff(repo: RepoPedidos, fila: Any) -> dict[str, Any]:
    pedido = await repo.pedido_completo(fila, con_celular=True)
    if pedido["pago"] is not None:
        # El id de transaccion de Wompi solo lo necesita el staff para conciliar.
        pedido["pago"] |= await repo.datos_de_pago_staff(fila.id)
    entregado_en = _a_datetime(pedido["envio"]["entregado_en"]) if pedido["envio"] else None
    return {
        **pedido,
        "historial": await repo.historial_de(fila.id),
        "devoluciones": await repo.devoluciones_de(fila.id, entregado_en),
    }


def _a_datetime(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso) if iso else None


# ---------------------------------------------------------------------------
# Escritura: checkout, pago y webhook (§9 del contrato)
# ---------------------------------------------------------------------------


class LineaOrden(BaseModel):
    """Un renglon que el acudiente aprobo. El precio que trae es el que VIO;
    Comercio lo re-verifica contra Catalogo y solo lo congela si sigue igual."""

    # Opcional: Comercio lo resuelve por sku contra Catalogo (endpoint interno),
    # en la misma lectura con que re-verifica el precio. Quien arma la orden
    # (Inteligencia, el navegador) nunca ve un id canonico -RPO cero, ADR 0017-,
    # asi que no puede mandarlo; se acepta si viene, pero no se exige.
    producto_canonico_id: str | None = None
    sku: str = Field(min_length=1, max_length=64)
    nombre: str = Field(min_length=1, max_length=256)
    cantidad: int = Field(gt=0)
    precio_unitario: int = Field(ge=0)
    matricula_id: str | None = None


class DireccionEntrega(BaseModel):
    """La direccion a la que se entrega. Se COPIA congelada en el envio (ADR
    0015): no es una llave a la libreta de Identidad.

    `telefono`/`departamento`/`documento_destinatario`/`indicaciones` son
    opcionales: el checkout legado manda solo los tres primeros y sigue
    cerrando. El formulario nuevo los exige del lado del cliente.

    `localidad` es el nombre canonico de una de las 20 de Bogota; aqui solo se
    valida el largo, porque la regla "obligatoria en Bogota" es del formulario y
    un cliente viejo tiene que seguir cerrando. `google_place_id` sale de la
    sugerencia de Google Places; nunca se reciben coordenadas (ADR 0044)."""

    destinatario: str = Field(min_length=1, max_length=256)
    direccion: str = Field(min_length=1, max_length=512)
    ciudad: str = Field(min_length=1, max_length=128)
    telefono: str | None = Field(default=None, max_length=32)
    departamento: str | None = Field(default=None, max_length=128)
    documento_destinatario: str | None = Field(default=None, max_length=64)
    indicaciones: str | None = Field(default=None, max_length=512)
    localidad: str | None = Field(default=None, max_length=64)
    google_place_id: str | None = Field(default=None, max_length=512)


class SolicitudOrden(BaseModel):
    """Lo que el checkout manda para crear una orden (FU-01)."""

    usuario_id: str
    trabajo_id: str | None = None
    hijos: int = Field(default=0, ge=0)
    colegios: list[str] = Field(default_factory=list)
    lineas: list[LineaOrden] = Field(min_length=1)
    entrega: DireccionEntrega


class SolicitudPago(BaseModel):
    """Lo que el checkout manda para iniciar el pago (FU-03)."""

    correo_cliente: str = Field(min_length=5, max_length=320)
    metodo: str = Field(default=MetodoPago.PSE.value, max_length=16)
    url_redireccion: str | None = None


class SolicitudRetracto(BaseModel):
    """Lo que el checkout manda para un retracto o devolucion (FU-04)."""

    motivo: str = Field(default="", max_length=512)


class SolicitudAvance(BaseModel):
    """Lo que el back-office de logistica manda para avanzar un pedido.

    `destino` es el siguiente estado de la cadena de entrega. Con reparto
    propio, el despacho trae nombre y celular del repartidor (y la fecha
    estimada); una incidencia trae su tipo y, si es `otro`, la nota. La validez
    de la transicion y de los datos la decide `validar_avance`: por eso
    `tipo_incidencia` es texto libre y no un `Literal`, para que el rechazo
    llegue con el mensaje del dominio y no como un 400 generico.

    `entrega_estimada` exige zona horaria (`AwareDatetime`): una fecha pelada
    seria medianoche sin zona y se correria al guardarla en `timestamptz`."""

    destino: str = Field(min_length=1, max_length=24)
    repartidor_nombre: str | None = Field(default=None, max_length=128)
    repartidor_celular: str | None = Field(default=None, max_length=32)
    tipo_incidencia: str | None = Field(default=None, max_length=32)
    nota: str | None = Field(default=None, max_length=512)
    entrega_estimada: AwareDatetime | None = None
    # Despacho por transportadora (alternativa al reparto propio): con ella, la guia es obligatoria.
    transportadora: str | None = Field(default=None, max_length=128)
    guia: str | None = Field(default=None, max_length=128)


def _uuid_o_422(valor: str, campo: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorDominio(
            "identificador_invalido",
            f"El campo {campo} no tiene forma de identificador.",
            estado=422,
            campo=campo,
        ) from None


@router.post("/v1/ordenes", status_code=201, summary="Crea una orden congelando precios")
async def crear_orden(request: Request, solicitud: SolicitudOrden) -> dict[str, Any]:
    """Re-verifica precio contra Catalogo, y solo entonces congela y reserva.

    La primera invariante del §9: antes de cerrar se relee el precio publico de
    cada linea; si cambio respecto al que el acudiente aprobo, la orden NO se
    cierra (`422 precio_cambiado`) y el acudiente decide sobre el precio nuevo.
    Si coincide, se congela en la linea (ADR 0012), se copia la direccion al
    envio (ADR 0015) y se crea la reserva de inventario. Nace `pendiente_pago`.

    La lectura de precios contra Catalogo (I/O de red) ocurre ANTES de abrir la
    sesion de base: nunca se sostiene una conexion de base a traves de una
    llamada HTTP externa.
    """
    usuario_id = _uuid_o_422(solicitud.usuario_id, "usuario_id")
    trabajo_id = _uuid_o_422(solicitud.trabajo_id, "trabajo_id") if solicitud.trabajo_id else None

    # Re-verificacion por HTTP contra Catalogo (no un cruce a su base). Sin
    # poder leer el precio no se cobra: Catalogo caido es 503, no un cobro a
    # ciegas. Cada sku se resuelve a (id canonico, precio vigente) y se arma la
    # linea resuelta que el dominio compara contra el precio aprobado.
    resueltas: list[LineaResuelta] = []
    for linea in solicitud.lineas:
        try:
            resuelto = await request.app.state.catalogo.resolver(linea.sku)
        except CatalogoCaido:
            raise ErrorDominio(
                "catalogo_no_disponible",
                "No se pudo re-verificar el precio con Catalogo; la orden no se cerro.",
                estado=503,
            ) from None
        resueltas.append(
            LineaResuelta(
                sku=linea.sku,
                precio_aprobado=linea.precio_unitario,
                cantidad=linea.cantidad,
                id_canonico=resuelto[0] if resuelto else None,
                precio_actual=resuelto[1] if resuelto else None,
            )
        )

    if reverificar_precios(resueltas):
        raise ErrorDominio(
            "precio_cambiado",
            "El precio de una o mas lineas cambio; revisa el nuevo precio antes de pagar.",
            estado=422,
            campo="lineas",
        )

    # Todos los precios coinciden: se arma la persistencia. El id resuelto por
    # Catalogo manda; si el cliente mando uno se respeta, pero la fuente de
    # verdad es el sku re-verificado arriba.
    por_sku = {r.sku: r for r in resueltas}
    lineas_persistir: list[dict[str, Any]] = []
    for linea in solicitud.lineas:
        id_canonico = por_sku[linea.sku].id_canonico
        producto_id = id_canonico or _uuid_o_422(linea.producto_canonico_id, "producto_canonico_id")
        matricula_id = _uuid_o_422(linea.matricula_id, "matricula_id") if linea.matricula_id else None
        lineas_persistir.append(
            {
                "matricula_id": matricula_id,
                "producto_id": producto_id,
                "sku": linea.sku,
                "nombre": linea.nombre,
                "cantidad": linea.cantidad,
                "precio_unitario": linea.precio_unitario,  # congelado (ADR 0012)
            }
        )

    # Un kit, un pedido pendiente. Si el acudiente vuelve a pulsar Pagar con lo
    # mismo, se reutiliza el pedido (Inteligencia le crea un intento de pago
    # nuevo); si cambio algo, el pendiente anterior se cancela, pero solo si
    # Wompi confirma que no tiene un pago aprobado o en curso.
    if trabajo_id is not None:
        reutilizable = await _resolver_pendientes_del_kit(request, usuario_id, trabajo_id, solicitud)
        if reutilizable is not None:
            return reutilizable

    pedido_id = uuid.uuid4()
    total = total_orden(resueltas)
    ahora = datetime.now(UTC)

    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        fila = await repo.insertar_orden(
            pedido_id=pedido_id,
            usuario_id=usuario_id,
            trabajo_id=trabajo_id,
            total=total,
            hijos=solicitud.hijos,
            colegios=list(solicitud.colegios),
            ahora=ahora,
            lineas=lineas_persistir,
            entrega=solicitud.entrega,
        )
        cuerpo = await repo.pedido_completo(fila)
    # Fuera del `async with`: la orden ya se persistio (commit sin excepcion). La
    # metrica de dominio T1 (ADR 0021) se cuenta aqui para no inflar el numero si
    # la transaccion hubiera hecho rollback.
    contar_orden_creada()
    return cuerpo


@router.post(
    "/v1/ordenes/{pedido_id}/pago",
    status_code=201,
    summary="Inicia el pago con la pasarela (FU-03)",
)
async def iniciar_pago(request: Request, pedido_id: uuid.UUID, solicitud: SolicitudPago) -> dict[str, Any]:
    """Crea la transaccion en la pasarela y guarda solo id + estado (SG-03).

    El medio de pago viaja a Wompi y no se persiste. `referencia_wompi` es el
    ancla por la que el webhook encontrara este pago mas tarde.
    """
    try:
        metodo = MetodoPago(solicitud.metodo)
    except ValueError:
        raise ErrorDominio(
            "metodo_invalido",
            "El medio de pago no es uno de los aceptados.",
            estado=422,
            campo="metodo",
        ) from None

    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await repo.obtener(pedido_id)
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
        if pedido.estado != EstadoPedido.PENDIENTE_PAGO.value:
            raise ErrorDominio(
                "pedido_no_pagable",
                "El pedido ya no esta pendiente de pago.",
                estado=409,
            )
        if vencido(pedido.creado_en):
            raise ErrorDominio(
                "pedido_vencido",
                "Este pedido tiene mas de 24 horas. Vuelve a armar tu kit para ver el precio de hoy.",
                estado=409,
            )

        # El intento numera la referencia (`-1`, `-2`, ...): un reintento tras
        # rechazo crea un pago nuevo, y sin el sufijo chocaria con el indice
        # unico de `referencia_wompi`. El webhook la busca por igualdad exacta,
        # asi que numerarla no cambia su lookup.
        intento = await repo.contar_pagos_pedido(pedido_id) + 1
        referencia = f"tukit-{pedido_id}-{intento}"
        try:
            creada = await request.app.state.pasarela.crear_transaccion(
                referencia=referencia,
                monto_centavos=int(pedido.total) * 100,
                correo_cliente=solicitud.correo_cliente,
                metodo=metodo.value,
                url_redireccion=solicitud.url_redireccion,
            )
        except httpx.HTTPError:
            # Wompi caido o devolviendo 5xx: nada se cobro y no se guarda pago.
            # 502, no 500: el fallo es del upstream, y el cliente puede
            # reintentar (la referencia numerada lo permite sin colision).
            raise ErrorDominio(
                "pasarela_no_disponible",
                "No se pudo contactar la pasarela de pago; intenta de nuevo en un momento.",
                estado=502,
            ) from None
        pago_id = uuid.uuid4()
        await repo.registrar_pago_iniciado(
            pago_id=pago_id,
            pedido_id=pedido_id,
            referencia_wompi=creada.referencia,
            transaccion_wompi=creada.transaccion_id,
            metodo=metodo.value,
            monto=int(pedido.total),
        )

    return {
        "pago_id": str(pago_id),
        "referencia_wompi": creada.referencia,
        "transaccion_wompi": creada.transaccion_id,
        "estado": EstadoPago.INICIADO.value,
        "url_redireccion": creada.url_redireccion,
        "widget": creada.widget,
    }


@router.post("/v1/webhooks/wompi", summary="Confirmacion asincrona de la pasarela")
async def webhook_wompi(request: Request, evento: dict[str, Any]) -> dict[str, Any]:
    """Aplica el resultado del pago una sola vez, aunque Wompi reintente.

    Verifica la firma (un evento que no la trae valida se ignora), y usa
    `evento_pasarela_procesado` como candado de idempotencia. En el flujo normal
    (Wompi reintenta en serie) un SELECT previo detecta el evento ya visto y se
    responde 200 sin re-aplicar; la insercion en la misma transaccion, con su
    indice unico, es el respaldo duro contra dos entregas simultaneas. En la
    primera aplicacion de un pago aprobado, transiciona el pedido a `pagado` y
    escribe `pedido_pagado` en la bandeja de salida DENTRO de la misma
    transaccion (patron outbox): el aviso al acudiente y el cambio de estado se
    guardan juntos o no se guardan.
    """
    pasarela = request.app.state.pasarela
    if not pasarela.verificar_firma(evento):
        # Firma que no cuadra: se ignora sin mover nada. 200 para que la
        # pasarela no reintente en bucle un evento que nunca vamos a aceptar.
        return {"estado": "ignorado", "motivo": "firma_invalida"}

    datos = pasarela.parsear_evento(evento)
    if not datos.evento_id or not datos.referencia or not datos.transaccion_id:
        return {"estado": "ignorado", "motivo": "evento_incompleto"}

    async with request.app.state.motor.sesion() as db:
        resultado = await _repo(await db.connection()).aplicar_resultado(datos)

    # Fuera del `async with`: se conto solo si el pago llevo el pedido a PAGADO y
    # la transaccion cerro bien (T3 de la saga, ADR 0021). El candado de
    # idempotencia evita contar dos veces un webhook repetido.
    if resultado.pagado:
        contar_pago_aprobado()

    if resultado.estado == "repetido":
        return {"estado": "repetido", "evento_id": datos.evento_id}
    if resultado.estado == "sin_pago":
        return {"estado": "sin_pago", "referencia": datos.referencia}
    if resultado.estado == "monto_no_coincide":
        return {"estado": "monto_no_coincide", "evento_id": datos.evento_id}
    return {
        "estado": "aplicado",
        "evento_id": datos.evento_id,
        "pago_estado": datos.estado.value,
        "pedido_transicionado": resultado.transicionado,
    }


@router.post(
    "/v1/pagos/{transaccion_id}/sincronizar",
    summary="Sincroniza el pago con la pasarela al regreso del acudiente",
)
async def sincronizar_pago(request: Request, transaccion_id: str) -> dict[str, Any]:
    """Consulta la transaccion en la pasarela y la aplica como lo hace el webhook.

    El acudiente vuelve del checkout alojado con el id de la transaccion en la
    URL; aqui se le pregunta a la pasarela su estado real (no se confia en lo que
    traiga el navegador) y se aplica con el mismo aplicador idempotente del
    webhook, asi que sincronizar y recibir el webhook no se pisan ni duplican el
    aviso.
    """
    try:
        datos = await request.app.state.pasarela.consultar_transaccion(transaccion_id)
    except TransaccionNoExiste:
        raise ErrorDominio(
            "transaccion_no_existe", "La pasarela no conoce esa transaccion", estado=404
        ) from None
    except PasarelaCaida:
        raise ErrorDominio(
            "pasarela_no_disponible", "No se pudo consultar la pasarela de pagos", estado=502
        ) from None

    resultado = await _aplicar_con_reintento(request, datos)
    if resultado.estado == "sin_pago" or resultado.pedido_id is None:
        raise ErrorDominio("pago_no_existe", "No hay un pago para esa transaccion", estado=404)
    async with request.app.state.motor.sesion() as db:
        pedido = await _repo(await db.connection()).pedido_de(resultado.pedido_id)
    return {
        "pedido_id": str(resultado.pedido_id),
        "total": int(pedido.total),
        "estado_pago": resultado.estado_pago,
        "estado_pedido": resultado.estado_pedido,
        "trabajo_id": str(pedido.trabajo_id) if pedido.trabajo_id is not None else None,
    }


async def _aplicar_con_reintento(request: Request, datos: EventoPasarela) -> ResultadoAplicacion:
    """Aplica un resultado en su propia sesion. Si el webhook llega a la vez, el
    segundo INSERT del candado choca con el indice unico: se reintenta UNA vez
    en una sesion nueva, donde la fila ya existe y el resultado es `repetido`."""
    for intento in range(2):
        try:
            async with request.app.state.motor.sesion() as db:
                resultado = await _repo(await db.connection()).aplicar_resultado(datos)
            if resultado.pagado:
                contar_pago_aprobado()
            return resultado
        except IntegrityError:
            if intento == 1:
                raise
    raise AssertionError("inalcanzable")


async def _revisar_pagos_en_wompi(request: Request, pedido_id: uuid.UUID) -> str:
    """Antes de cancelar: `pagado`, `en_curso` o `libre`.

    Un PSE puede estar en curso, o ya aprobado, sin que Tukit lo sepa (el
    acudiente no volvio y no hay webhook). Se busca en Wompi cada intento que
    aqui sigue `iniciado`; uno aprobado se aplica en el acto (el pedido pasa a
    `pagado`) y uno rechazado se anota. Si Wompi no responde, `PasarelaCaida`
    sube: sin saberlo no se cancela.
    """
    async with request.app.state.motor.sesion() as db:
        referencias = await _repo(await db.connection()).referencias_iniciadas(pedido_id)
    en_curso = False
    for referencia in referencias:
        evento = await request.app.state.pasarela.consultar_por_referencia(referencia)
        if evento is None:
            continue
        if evento.estado == EstadoPago.INICIADO:
            en_curso = True
            continue
        resultado = await _aplicar_con_reintento(request, evento)
        if resultado.estado_pedido == EstadoPedido.PAGADO.value:
            return "pagado"
    return "en_curso" if en_curso else "libre"


async def _cancelar_si_se_puede(request: Request, pedido_id: uuid.UUID) -> str:
    """Cancela un pedido pendiente y libera su reserva, si Wompi lo permite.

    Devuelve `cancelado`, `pagado`, `en_curso` o `no_cancelable`.
    """
    async with request.app.state.motor.sesion() as db:
        pedido = await _repo(await db.connection()).obtener(pedido_id)
    if pedido is None or pedido.estado != EstadoPedido.PENDIENTE_PAGO.value:
        return "no_cancelable"
    revision = await _revisar_pagos_en_wompi(request, pedido_id)
    if revision != "libre":
        return revision
    async with request.app.state.motor.sesion() as db:
        cancelado = await _repo(await db.connection()).cancelar_pendiente(pedido_id)
    return "cancelado" if cancelado else "no_cancelable"


async def _resolver_pendientes_del_kit(
    request: Request, usuario_id: uuid.UUID, trabajo_id: uuid.UUID, solicitud: SolicitudOrden
) -> dict[str, Any] | None:
    """El pedido pendiente a reutilizar para este kit, o `None` para crear uno.

    Uno identico y vigente se reutiliza. Los demas pendientes del mismo kit se
    cancelan con la revision de Wompi; uno con pago en curso o aprobado se deja
    como esta (cancelarlo podria cobrar sin entregar), y si Wompi no responde
    tambien se deja: duplicar es mejor que cancelar a ciegas.
    """
    # La entrega compara toda la copia congelada salvo el place_id, localidad
    # incluida: ver `CAMPOS_FIRMA_ENTREGA`.
    buscada = firma_orden(
        [(linea.sku, linea.cantidad, linea.precio_unitario) for linea in solicitud.lineas],
        tuple(getattr(solicitud.entrega, campo) for campo in CAMPOS_FIRMA_ENTREGA),
    )
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pendientes = await repo.pendientes_del_kit(usuario_id, trabajo_id)
        for pedido in pendientes:
            if vencido(pedido.creado_en):
                continue
            lineas, entrega = await repo.contenido_de(pedido.id)
            if firma_orden(lineas, entrega) == buscada:
                return await repo.pedido_completo(pedido)

    for pedido in pendientes:
        try:
            await _cancelar_si_se_puede(request, pedido.id)
        except PasarelaCaida:
            continue
    return None


@router.post(
    "/v1/ordenes/{pedido_id}/cancelar",
    summary="Cancela un pedido pendiente de pago, si Wompi no tiene un pago en curso",
)
async def cancelar_orden(request: Request, pedido_id: uuid.UUID) -> dict[str, Any]:
    """El acudiente cancela un pedido que no pago. Antes se le pregunta a Wompi
    por cada intento: cancelar con un PSE aprobado o en curso cobraria sin
    entregar. Cancelado, la reserva de inventario se libera."""
    async with request.app.state.motor.sesion() as db:
        existe = await _repo(await db.connection()).obtener(pedido_id)
    if existe is None:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)
    try:
        resultado = await _cancelar_si_se_puede(request, pedido_id)
    except PasarelaCaida:
        raise ErrorDominio(
            "pasarela_no_disponible",
            "No pudimos confirmar con Wompi que no tengas un pago en curso. Intenta en unos minutos.",
            estado=502,
        ) from None
    if resultado == "pagado":
        raise ErrorDominio(
            "pedido_ya_pagado",
            "Tu pago de este pedido ya fue aprobado, asi que no lo cancelamos.",
            estado=409,
        )
    if resultado == "en_curso":
        raise ErrorDominio(
            "pago_en_curso",
            "Tu pago todavia se esta procesando. Espera la respuesta de tu banco antes de cancelar.",
            estado=409,
        )
    if resultado == "no_cancelable":
        raise ErrorDominio(
            "pedido_no_cancelable", "Solo se pueden cancelar pedidos pendientes de pago.", estado=409
        )
    return await ver_orden(request, pedido_id)


@router.get("/v1/ordenes/{pedido_id}", summary="Seguimiento de una orden (FU-01 + UM-03)")
async def ver_orden(request: Request, pedido_id: uuid.UUID) -> dict[str, Any]:
    # Interna (la puerta no la expone): reusa el serializador del pedido, sin el
    # celular del repartidor ni el historial, que son solo del detalle staff.
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        return await repo.pedido_completo(await _pedido_o_404(repo, pedido_id))


# ---------------------------------------------------------------------------
# El acudiente sobre SUS pedidos: ver, pagar y cancelar desde su panel
# ---------------------------------------------------------------------------
#
# `/v1/ordenes/*` no sale por la puerta (solo `avanzar`): sin sesion, cualquiera
# con el id de un pedido podria pagarlo o cancelarlo. Estas tres rutas son las
# mismas operaciones con la puerta del portador: el `usuario_id` sale del token
# y un pedido ajeno responde 404, igual que uno que no existe, para no confirmar
# que existe.


async def _pedido_del_portador(request: Request, pedido_id: uuid.UUID, authorization: str | None) -> None:
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        pedido = await _repo(await db.connection()).obtener(pedido_id)
    if pedido is None or pedido.usuario_id != usuario_id:
        raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)


@router.get("/v1/comercio/mis-pedidos/{pedido_id}", summary="Uno de MIS pedidos, sin datos del reparto")
async def ver_mi_pedido(
    request: Request, pedido_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """El pedido de la ruta interna mas su `linea_de_tiempo` para `/pedidos/[id]`.

    La linea la arma `dominio.linea_de_tiempo` con vistas que no traen actor,
    correo de staff, nota ni el celular del repartidor: el acudiente ve QUE paso
    y CUANDO, no QUIEN lo movio."""
    await _pedido_del_portador(request, pedido_id, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        fila = await _pedido_o_404(repo, pedido_id)
        pedido = await _con_seguimiento(repo, await repo.pedido_completo(fila))
        pagos, historial, envio = await repo.vistas_para_linea_de_tiempo(fila.id)
    # La linea de tiempo de `/pedidos/[id]` es la de `dominio.linea_de_tiempo`;
    # `seguimiento` y `retracto` (panel) viajan al lado.
    return {
        **pedido,
        "linea_de_tiempo": linea_de_tiempo(
            estado=fila.estado, creado_en=fila.creado_en, pagos=pagos, historial=historial, envio=envio
        ),
    }


@router.post(
    "/v1/comercio/mis-pedidos/{pedido_id}/pago",
    status_code=201,
    summary="Paga uno de MIS pedidos pendientes",
)
async def pagar_mi_pedido(
    request: Request,
    pedido_id: uuid.UUID,
    solicitud: SolicitudPago,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _pedido_del_portador(request, pedido_id, authorization)
    return await iniciar_pago(request, pedido_id, solicitud)


@router.post(
    "/v1/comercio/mis-pedidos/{pedido_id}/cancelar",
    summary="Cancela uno de MIS pedidos pendientes, si Wompi no tiene un pago en curso",
)
async def cancelar_mi_pedido(
    request: Request, pedido_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _pedido_del_portador(request, pedido_id, authorization)
    return await cancelar_orden(request, pedido_id)


@router.post(
    "/v1/comercio/mis-pedidos/{pedido_id}/retracto",
    status_code=201,
    summary="El acudiente ejerce el retracto de UNO de sus pedidos (Ley 1480, art. 47)",
)
async def retractar_mi_pedido(
    request: Request,
    pedido_id: uuid.UUID,
    solicitud: SolicitudRetracto,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Solo el dueno del pedido, y solo dentro del plazo: 5 dias habiles desde la entrega.

    El `usuario_id` sale de la sesion. Un pedido ajeno responde 403 (no se
    revela nada que no se supiera: el id es un UUID imposible de adivinar) y uno
    que no existe, 404. Antes de la entrega el retracto cancela el pedido y
    marca el pago para reembolso; ya entregado, deja la solicitud registrada y el
    equipo coordina la recogida y el reembolso. Pedirlo dos veces no abre dos.
    """
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await _pedido_o_404(repo, pedido_id)
        if pedido.usuario_id != usuario_id:
            raise ErrorDominio(
                "pedido_ajeno", "Este pedido no es de tu cuenta, así que no puedes pedir su retracto.", estado=403
            )
        envio = (await repo.pedido_completo(pedido)).get("envio") or {}
        previa = await repo.devolucion_de(pedido_id)
        estado = evaluar_retracto(
            pedido.estado, _fecha(envio.get("entregado_en")), _ahora(), ya_solicitado=previa is not None
        )
        if not estado.puede:
            raise ErrorDominio(
                f"retracto_{estado.razon}",
                _MENSAJE_RETRACTO.get(estado.razon or "", "Este pedido no admite retracto."),
                estado=409,
            )

        devolucion_id = uuid.uuid4()
        await repo.registrar_devolucion(
            devolucion_id=devolucion_id,
            pedido_id=pedido_id,
            usuario_id=pedido.usuario_id,
            motivo=solicitud.motivo,
            monto=int(pedido.total),
        )
        # Si la maquina de estados no deja cancelar (ya despachado, en reparto),
        # queda la solicitud registrada para que el equipo detenga el envio.
        cancelado = estado.antes_de_entrega and transicion_valida(pedido.estado, EstadoPedido.CANCELADO.value)
        if cancelado:
            await repo.cancelar_pedido(pedido_id)
            await repo.marcar_pago_reembolsado(pedido_id)

    return {
        "devolucion_id": str(devolucion_id),
        "pedido_id": str(pedido_id),
        "cancelado": cancelado,
        "estado": EstadoPedido.CANCELADO.value if cancelado else pedido.estado,
        "monto": int(pedido.total),
    }


_MENSAJE_RETRACTO = {
    "ya_solicitado": "Ya pediste el retracto de este pedido. Te escribiremos con los pasos.",
    "plazo_vencido": "El plazo de 5 días hábiles desde la entrega ya terminó.",
    "sin_pagar": "Este pedido no se pagó, así que no hay nada que devolver. Puedes cancelarlo desde Mis pedidos.",
    "cancelado": "Este pedido ya está cancelado.",
    "sin_fecha_de_entrega": "No tenemos la fecha de entrega de este pedido. Escríbenos desde Mis casos y lo resolvemos.",
    "estado_no_permite": "Este pedido no admite retracto en su estado actual.",
}


@router.post("/v1/ordenes/{pedido_id}/retracto", status_code=201, summary="Retracto o devolucion (FU-04)")
async def retractar_orden(
    request: Request, pedido_id: uuid.UUID, solicitud: SolicitudRetracto
) -> dict[str, Any]:
    """Registra la devolucion, cancela el pedido si la transicion lo permite y
    marca el pago para reembolso. El monto del reembolso es el total pagado."""
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await repo.obtener(pedido_id)
        if pedido is None:
            raise ErrorDominio("pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404)

        cancelable = transicion_valida(pedido.estado, EstadoPedido.CANCELADO.value)
        devolucion_id = uuid.uuid4()
        await repo.registrar_devolucion(
            devolucion_id=devolucion_id,
            pedido_id=pedido_id,
            usuario_id=pedido.usuario_id,
            motivo=solicitud.motivo,
            monto=int(pedido.total),
        )
        if cancelable:
            await repo.cancelar_pedido(pedido_id)
            await repo.marcar_pago_reembolsado(pedido_id)

    return {
        "devolucion_id": str(devolucion_id),
        "pedido_id": str(pedido_id),
        "cancelado": cancelable,
        "estado": EstadoPedido.CANCELADO.value if cancelable else pedido.estado,
    }


_MENSAJE_AVANCE = {
    "destino_invalido": "El estado destino no es uno de los del pedido.",
    "transicion_invalida": "No se puede pasar el pedido a ese estado desde el actual.",
    "despacho_incompleto": "Para despachar hacen falta el nombre y el celular del repartidor, o una transportadora con su guia.",
    "despacho_sin_guia": "Con transportadora, el numero de guia es obligatorio.",
    "incidencia_sin_tipo": "Una incidencia necesita su tipo.",
    "tipo_incidencia_invalido": "Ese tipo de incidencia no existe.",
    "incidencia_sin_nota": "Si la incidencia es 'otro', describe lo ocurrido en la nota.",
}


@router.post("/v1/ordenes/{pedido_id}/avanzar", summary="Avanza un pedido por la cadena de entrega")
async def avanzar_pedido(
    request: Request,
    pedido_id: uuid.UUID,
    solicitud: SolicitudAvance,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Empuja el pedido al siguiente estado de entrega: solo staff.

    Que la transicion sea legal y le toque al back-office, y que vengan los
    datos que el destino exige, lo decide `validar_avance`; un rechazo se
    traduce a su sobre con el codigo y el campo que trae. Si acepta, en UNA
    unidad de trabajo (todo o nada): el cambio de estado guardado contra
    carreras, el sello del envio, la fila de historial con el actor, el aviso
    al acudiente en la bandeja y, al cancelar, el pago marcado para reembolso
    (como el retracto).
    """
    actor = await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = _repo(await db.connection())
        pedido = await _pedido_o_404(repo, pedido_id)

        entradas = {
            "repartidor_nombre": solicitud.repartidor_nombre,
            "repartidor_celular": solicitud.repartidor_celular,
            "tipo_incidencia": solicitud.tipo_incidencia,
            "nota": solicitud.nota,
            "transportadora": solicitud.transportadora,
            "guia": solicitud.guia,
        }
        rechazo = validar_avance(pedido.estado, solicitud.destino, **entradas)
        if rechazo is not None:
            raise ErrorDominio(
                rechazo.razon,
                _MENSAJE_AVANCE.get(rechazo.razon, "El avance del pedido no procede."),
                estado=rechazo.estado,
                campo=rechazo.campo,
            )
        avance = preparar_avance(solicitud.destino, **entradas)

        movido = await repo.avanzar_despacho(
            pedido_id=pedido_id,
            desde=pedido.estado,
            destino=solicitud.destino,
            repartidor_nombre=avance.repartidor_nombre,
            repartidor_celular=avance.repartidor_celular,
            entrega_estimada=solicitud.entrega_estimada,
            transportadora=avance.transportadora,
            guia=avance.guia,
        )
        if not movido:
            # Otro avance gano la carrera entre la lectura y el UPDATE. Lanzar
            # revierte la unidad de trabajo: no queda historial ni aviso huerfano.
            raise ErrorDominio(
                "avance_concurrente",
                "Alguien mas movio este pedido mientras tanto; recarga y vuelve a intentar.",
                estado=409,
            )
        await repo.registrar_historial(
            pedido_id=pedido_id,
            estado_desde=pedido.estado,
            estado_hacia=solicitud.destino,
            actor_id=actor.usuario_id,
            actor_correo=actor.correo,
            nota=avance.nota,
            tipo_incidencia=avance.tipo_incidencia,
        )
        if avance.aviso is not None:
            await repo.encolar_aviso_pedido(
                pedido, avance.aviso, repartidor=avance.repartidor_nombre or avance.transportadora
            )
        if solicitud.destino == EstadoPedido.CANCELADO.value:
            # Como el retracto: el pedido cancelado deja su pago aprobado marcado
            # para reembolso, en la misma transaccion.
            await repo.marcar_pago_reembolsado(pedido_id)

        return await _detalle_staff(repo, await repo.obtener(pedido_id))
