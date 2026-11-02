"""El recurso `trabajo`: crear, procesar por etapas, consultar y revisar.

Aqui vive la maquina de estados que el contrato promete y la orquestacion de
las cuatro etapas. Lo que hay que entender de este modulo es que **el estado
no vive en el proceso**: cada transicion y cada etapa se escriben en la base
antes de seguir. La consecuencia practica es que reiniciar el servicio no
pierde los trabajos en vuelo, que `GET /v1/trabajos/{id}` puede responder
desde otro proceso, y que reanudar no vuelve a pagar la percepcion, que es la
etapa cara.

La ejecucion de fondo es DURABLE (ADR 0024): `lanzar` solo deja el trabajo
`encolado`, y `tukit_inteligencia.trabajador` lo drena con `SELECT … FOR UPDATE
SKIP LOCKED` —el mismo mecanismo del outbox—, lo mueve a `procesando` y corre
`procesar`. Una caida de proceso ya no pierde el trabajo: la fila sigue en la
base y otro worker (o el reinicio) la retoma. `procesar` es idempotente en el
claim (borra ITEM/KIT y reejecuta), asi que retomar no duplica.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, insert, select, update
from tukit_comun.broker import url_broker
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.consumidor import marcar_procesado

from .dominio.pipeline import (
    _anclar_kits,
    _candidato,
    _normalizar,
    _personaje_pedido,
    estado_desde_emparejamiento,
    inyectar_personaje_fan,
)
from .modelos import (
    Base,
    EstadoEtapa,
    EstadoResolucion,
    EstadoTrabajo,
    PerfilKit,
    puede_pasar,
)
from .modelos.trabajo import ETAPAS
from .optimizador import (
    CONCEPTOS_ANCLA,
    ORDEN_NIVEL,
    Candidato,
    Renglon,
    armar_los_tres,
    unidades_a_comprar,
)
from .parseo import BUSCA_EN_CATALOGO, Demanda, mensaje_para_papa
from .remoto import ClienteCatalogo, ClienteComercio, ClienteIdentidad, RemotoCaido
from .repositorios.trabajos import RepoTrabajos, TrabajoNoExiste, TransicionIlegal

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
ETAPA = Base.metadata.tables["etapa_trabajo"]
ITEM = Base.metadata.tables["item_crudo"]
CANDIDATO = Base.metadata.tables["candidato_item"]
RESOLUCION = Base.metadata.tables["resolucion_item"]
TRANSICION = Base.metadata.tables["transicion_resolucion"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
KIT_CANONICO = Base.metadata.tables["kit_canonico"]
IMPORTACION = Base.metadata.tables["importacion_lista"]

# Umbral de confianza por encima del cual el emparejamiento se da por bueno
# sin que lo mire una persona. Es la tau configurable que pide PE-04, y se
# lee del entorno para poder subirla cuando el catalogo este mas completo sin
# tocar codigo.
TAU_POR_OMISION = 0.75

ANIO_LECTIVO_POR_OMISION = 2026


def tau() -> float:
    try:
        return float(os.environ.get("TUKIT_TAU", TAU_POR_OMISION))
    except ValueError:
        return TAU_POR_OMISION


def autopublicar() -> bool:
    """Atajo de DESARROLLO que se salta la revision humana.

    El contrato es claro en que el acudiente nunca ve un kit sin revisar: esa
    es la razon de ser de `espera_revision` y de AD-06. Pero mientras se
    construye el frontend, exigir una segunda llamada para ver la primera
    pantalla es friccion pura, asi que existe la valvula y **se anuncia al
    arrancar**. Una valvula silenciosa seria peor que no tenerla: alguien la
    dejaria puesta en produccion sin enterarse.
    """
    return os.environ.get("TUKIT_AUTOPUBLICAR", "").strip().lower() in {"1", "true", "si"}


def ahora() -> datetime:
    return datetime.now(UTC)


class SolicitudNoCancelable(Exception):
    """El acudiente pidio cancelar una solicitud que no se puede cancelar.

    Lleva el codigo y el estado HTTP que la API devuelve tal cual, para que el
    panel le diga al papa el motivo exacto (p. ej. que primero cancele el pedido).
    """

    def __init__(self, codigo: str, mensaje: str, estado: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado = estado


class CambioNoPermitido(Exception):
    """El acudiente pidio un cambio de producto que no se puede hacer.

    Lleva el codigo y el estado HTTP que la API devuelve tal cual, para que la
    pantalla le diga al papa el motivo exacto.
    """

    def __init__(self, codigo: str, mensaje: str, estado: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado = estado


class CheckoutRechazado(Exception):
    """Comercio rechazo la orden por una razon de negocio (p.ej. precio cambio).

    Lleva el estado HTTP y el cuerpo de Comercio para que el acudiente vea el
    motivo exacto (`precio_cambiado` y el nuevo precio), no un 500 generico.
    """

    def __init__(self, estado: int, cuerpo: dict[str, Any]) -> None:
        super().__init__(str(cuerpo.get("error") or estado))
        self.estado = estado
        self.cuerpo = cuerpo


class TrabajoProtegido(Exception):
    """Un trabajo `publicado` no se borra: es (o alimenta) el kit canonico."""

    def __init__(self, estado: str) -> None:
        super().__init__(f"un trabajo en {estado} esta protegido contra borrado")
        self.estado = estado


class SinProductoQueValidar(Exception):
    """Validar una linea exige un producto, y esta no tiene ninguno.

    Ni llego `sku`, ni la linea del kit tiene producto, ni la resolucion
    apuntaba a un candidato —o el `sku` pedido no existe en el catalogo—. Se
    rechaza aqui, con un motivo, en vez de dejar que el CHECK
    `resolucion_resuelta_tiene_candidato` lo convierta en un 500.
    """

    def __init__(self, sku: str | None) -> None:
        super().__init__(sku or "sin_sku")
        self.sku = sku


class PreviewNoPublicable(Exception):
    """Un `preview_onboarding` no se publica: no tiene acudiente. Se aprueba la
    LISTA (Catalogo), que si crea el colegio y arma el trabajo del padre."""


class NoCanonizable(Exception):
    """Solo un trabajo SIN acudiente (un preview o el canonico de una lista) se
    fija a mano como kit canonico: el de un padre lleva sus preferencias y su
    tope, y no puede servirle a otro."""


class KitsPublicadosNoEditables(Exception):
    """Los kits canonicos publicados no se editan en sitio: hay acudientes que
    apuntan a ellos y deben seguir viendo lo que pagaron. Se edita su version
    siguiente con `abrir_borrador` («Editar kits»)."""


class BorradorDesactualizado(Exception):
    """El canonico que se quiere editar (o del que salio el borrador) ya no es
    el vigente de su grado: otro lo reemplazo mientras tanto, y publicar el
    borrador pisaria esa version mas nueva."""


# El trabajo que arma los kits canonicos de una lista recien aprobada. No tiene
# acudiente ni preferencias: son los tres kits de siempre (Ahorrador, Fan,
# Premium) que la ruta rapida le aplica a cualquier padre que no pida tope.
ORIGEN_CANONICO = "canonico_lista"

# Los origenes que no tienen a quien avisar: publicarlos no emite
# `kits_publicados`, solo fija la cache canonica del grado.
ORIGENES_SIN_ACUDIENTE = frozenset({"preview_onboarding", ORIGEN_CANONICO})


# ---------------------------------------------------------------------------
# Creacion
# ---------------------------------------------------------------------------


class EventoRepetido(Exception):
    """El evento que pedia el trabajo ya se habia procesado: no se crea otro."""


async def crear(
    motor: Any,
    *,
    hijos: list[dict[str, Any]],
    contacto: dict[str, Any] | None = None,
    preferencias: dict[str, Any] | None = None,
    origen: str = "colegio_grado",
    identidad: ClienteIdentidad | None = None,
    usuario_id: uuid.UUID | None = None,
    en_proceso: bool = False,
    evento: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """Crea el trabajo en `encolado` y devuelve el cuerpo del 202.

    `en_proceso` lo crea ya `procesando`, para quien lo va a procesar en el acto
    (el poller y el preview del admin). Si naciera `encolado`, el trabajador
    durable (ADR 0024) podria reclamarlo entre el INSERT y el `procesar` del
    llamador, y los dos armarian los kits a la vez. `procesando` lo saca del
    claim normal; si el llamador muere a mitad, el trabajador lo retoma con su
    pasada de colgados, igual que cualquier otro.

    El contacto se registra en Identidad y aqui solo queda su identificador.
    Si Identidad no responde, el trabajo se crea igual con la degradacion
    anotada: perder el aviso es malo, perder el kit por no poder avisar es
    peor.

    `usuario_id` permite crear el trabajo para un acudiente YA identificado sin
    volver a llamar a Identidad: es lo que usa el poller de `lista_verificada`,
    donde el padre subio su lista hace rato y su `usuario_id` ya vive en la
    tarea. Si viene, gana sobre `contacto` (no se re-registra nada).

    `evento` es el `(origen, id)` del evento que pide el trabajo, cuando llega
    por una cola de RabbitMQ (ADR 0046). Se anota en `evento_procesado` en la
    misma transaccion que el trabajo; si ya estaba, no se crea nada y levanta
    `EventoRepetido`. Asi un evento entregado dos veces no arma dos kits, aunque
    el proceso haya caido entre crear el trabajo y confirmar el mensaje.

    Con RabbitMQ, un trabajo que nace `encolado` deja su aviso
    `trabajo_encolado` en la bandeja, en la misma transaccion (ADR 0046).
    """
    degradaciones: list[dict[str, Any]] = []
    if usuario_id is None and contacto and contacto.get("correo"):
        cliente = identidad or ClienteIdentidad()
        crudo = await cliente.registrar_contacto(str(contacto["correo"]), contacto.get("celular"))
        if crudo:
            usuario_id = uuid.UUID(crudo)
        else:
            degradaciones.append(
                {
                    "dependencia": "identidad",
                    "efecto": "el trabajo corre sin destinatario: no habra aviso al terminar",
                    "lineas_afectadas": 0,
                }
            )

    cifrador = cifrador_desde_entorno()
    trabajo_id = uuid.uuid4()

    async with motor.engine.begin() as conexion:
        if evento is not None and not await marcar_procesado(conexion, *evento):
            raise EventoRepetido(f"{evento[0]}:{evento[1]}")
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id,
                usuario_id=usuario_id,
                estado=(EstadoTrabajo.PROCESANDO if en_proceso else EstadoTrabajo.ENCOLADO).value,
                origen=origen,
                hijos=hijos,
                preferencias_cifradas=cifrador.cifrar_json(preferencias or {}),
                degradaciones=degradaciones,
                estimado_segundos=180,
            )
        )
        # Las cuatro etapas nacen en `pendiente` y no se crean sobre la
        # marcha. Asi el frontend puede pintar la barra completa desde el
        # primer momento y la espera tiene forma, en vez de ser un giro
        # indefinido que no dice cuanto falta.
        await conexion.execute(
            insert(ETAPA),
            [{"id": uuid.uuid4(), "trabajo_id": trabajo_id, "nombre": nombre} for nombre in ETAPAS],
        )
        if not en_proceso:
            await _avisar_encolado(conexion, trabajo_id)

    return {
        "trabajo_id": str(trabajo_id),
        "estado": EstadoTrabajo.ENCOLADO.value,
        "estimado_segundos": 180,
        "consultar_en": f"/v1/trabajos/{trabajo_id}",
        "degradaciones": degradaciones,
    }


# ---------------------------------------------------------------------------
# Etapas
# ---------------------------------------------------------------------------


async def _marcar_etapa(
    conexion: Any,
    trabajo_id: uuid.UUID,
    nombre: str,
    estado: str,
    *,
    ms: int | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    await RepoTrabajos(conexion).marcar_etapa(trabajo_id, nombre, estado, ms=ms, detalle=detalle)


async def _estado(conexion: Any, trabajo_id: uuid.UUID) -> str:
    return await RepoTrabajos(conexion).estado(trabajo_id)


async def _pasar_a(conexion: Any, trabajo_id: uuid.UUID, nuevo: str, **extra: Any) -> None:
    await RepoTrabajos(conexion).pasar_a(trabajo_id, nuevo, **extra)


async def _listas_por_hijo(
    catalogo: ClienteCatalogo, hijos: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resuelve la lista oficial vigente de cada hijo (metadatos, no items).

    Devuelve `(encontradas, sin_lista)`: cada entrada de `encontradas` trae la
    referencia del hijo, la lista completa (`lista()`), su `version_id` y si
    esta `revisada`. Es el paso comun a las dos rutas —la lenta lee los items
    de aqui, la rapida solo mira `revisada`/`version_id`— para no llamar dos
    veces al catalogo por lo mismo.
    """
    encontradas: list[dict[str, Any]] = []
    sin_lista: list[dict[str, Any]] = []

    for hijo in hijos:
        referencia = str(hijo.get("referencia") or "hijo-1")
        colegio_id = str(hijo.get("colegio_id") or "")
        grado = str(hijo.get("grado") or "")
        anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)

        # Un hijo con `version_id` explicito (el preview de una edicion) fija la
        # version a leer: se trae POR SU ID —no la vigente—, para previsualizar
        # un borrador que aun no es vigente. `revision()` devuelve la misma forma
        # que `lista()`, asi que el resto del pipeline no distingue. El flujo del
        # acudiente y el del poller no traen `version_id`: caen a la vigente,
        # como siempre.
        version_pedida = hijo.get("version_id")
        if version_pedida:
            completa = await catalogo.revision(str(version_pedida))
            encontradas.append(
                {
                    "hijo": referencia,
                    "colegio_id": colegio_id,
                    "completa": completa,
                    "version_id": completa.get("version_id") or version_pedida,
                    "revisada": bool(completa.get("revisada")),
                }
            )
            continue

        listas = await catalogo.listas(colegio_id=colegio_id, grado=grado, anio_lectivo=anio)
        if not listas:
            sin_lista.append({"hijo": referencia, "colegio_id": colegio_id, "grado": grado})
            continue

        completa = await catalogo.lista(listas[0]["lista_id"])
        encontradas.append(
            {
                "hijo": referencia,
                "colegio_id": colegio_id,
                "completa": completa,
                "version_id": completa.get("version_id") or listas[0].get("version_id"),
                "revisada": bool(completa.get("revisada")),
            }
        )

    return encontradas, sin_lista


async def alguna_lista_para(catalogo: ClienteCatalogo, hijos: list[dict[str, Any]]) -> bool:
    """True si al menos un hijo tiene una lista que leer en el catalogo.

    Es la condicion sin la que `procesar` termina en `sin_lista_oficial`; crear
    la pregunta antes para rechazar en el acto en vez de encolar un trabajo que
    va a fallar (H-C-03). Mismo anio por omision que `_listas_por_hijo`. Con el
    catalogo caido no se sabe: se responde True y el trabajo se encola como
    siempre, que el trabajador ya sabe esperar al catalogo.
    """
    for hijo in hijos:
        if hijo.get("version_id"):
            return True
        anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
        try:
            if await catalogo.listas(
                colegio_id=str(hijo.get("colegio_id") or ""),
                grado=str(hijo.get("grado") or ""),
                anio_lectivo=anio,
            ):
                return True
        except RemotoCaido:
            return True
    return False


async def _renglones_de_listas(
    catalogo: ClienteCatalogo, hijos: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Trae la lista oficial vigente de cada (colegio, grado).

    Un hijo sin lista publicada no tumba el trabajo: se anota cual falto y el
    resto sigue. Es la misma regla que en todas partes, decir que falta es
    mejor que devolver un kit que parece completo.
    """
    renglones: list[dict[str, Any]] = []
    detalle: dict[str, Any] = {"listas": [], "sin_lista": []}

    encontradas, sin_lista = await _listas_por_hijo(catalogo, hijos)
    detalle["sin_lista"] = sin_lista

    for entrada in encontradas:
        referencia = entrada["hijo"]
        completa = entrada["completa"]
        detalle["listas"].append(
            {
                "hijo": referencia,
                "lista_id": completa["lista_id"],
                "grado": completa["grado"],
                "items": completa["total_items"],
            }
        )
        for item in completa["items"]:
            renglones.append(
                {
                    "hijo": referencia,
                    "orden": item["orden"],
                    "texto": item["texto_original"],
                    "cantidad": item["cantidad"],
                    "instruccion_colegio": item.get("instruccion_colegio"),
                    "url_externa": item.get("url_externa"),
                    "tipo_item_lista": item.get("tipo_item"),
                    "modo_lista": item.get("modo_adquisicion"),
                    "concepto_lista": (item.get("concepto") or {}).get("codigo"),
                }
            )

    return renglones, detalle


def _mensaje_por_tipo(texto: str, tipo: str, modo: str) -> str:
    """El aviso de una linea que no se busca en el catalogo, por su tipo y modo."""
    return mensaje_para_papa(Demanda(texto=texto, tipo_item=tipo, modo_adquisicion=modo, cantidad=1))


def _tipo_del_concepto_manda(renglon: dict[str, Any], respuesta: dict[str, Any]) -> bool:
    """Si el concepto reconocido dice que el renglon NO se compra en el catalogo.

    El parseo adivina el tipo por el texto y casi siempre dice `util`; el
    concepto es un dato curado ("Uniforme", "Lo entrega el colegio",
    "Audifonos de diadema" como `otro`). Cuando el concepto no se surte, el
    renglon toma su tipo y queda como linea informativa, igual que en la ruta
    rapida: sin esto, la previsualizacion intentaba venderle un uniforme al
    acudiente y mostraba "sin producto". Un tipo que la lista oficial ya
    declaro para el renglon manda sobre el del concepto.

    Muta el renglon (es el mismo dict que lee la optimizacion) y devuelve si
    hay que sacarlo de la resolucion.
    """
    tipo = respuesta.get("concepto_tipo_item")
    if not tipo or tipo in BUSCA_EN_CATALOGO or renglon.get("tipo_item_lista"):
        return False
    renglon["tipo_item"] = tipo
    renglon["busca_en_catalogo"] = False
    renglon["mensaje"] = _mensaje_por_tipo(renglon["texto"], tipo, renglon["modo_adquisicion"])
    return True


async def _escribir_kits(
    conexion: Any,
    trabajo_id: uuid.UUID,
    kits: list[Any],
    ids_item: dict[tuple[str, int], uuid.UUID],
    preferencias: dict[str, Any],
    cifrador: Any,
    *,
    ms: int,
) -> None:
    """Persiste KIT+LINEA y marca la etapa de optimizacion. Comun a las dos rutas."""
    await RepoTrabajos(conexion).escribir_kits(trabajo_id, kits, ids_item, preferencias, cifrador, ms=ms)


async def _finalizar(motor: Any, trabajo_id: uuid.UUID, *, publicar_directo: bool = False) -> str:
    """El cierre comun: publicar (y avisar) o dejar en espera de revision.

    `publicar_directo` es para el kit que un administrador YA autorizo al
    aprobar la lista del padre (origen 'lista_verificada'): la revision humana
    ocurrio sobre la LISTA, y el padre revisa el KIT resultante desde el enlace
    de pre-compra del correo. Ahi no hay una segunda cola de revision —seria
    pedirle a una persona que apruebe lo que ya aprobo—, asi que se publica
    directo y se emite `kits_publicados` para que el repartidor le avise. La
    valvula de desarrollo (`autopublicar`) hace lo mismo para todos los origenes.
    """
    async with motor.engine.begin() as conexion:
        origen = await conexion.scalar(select(TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id))
        if origen == ORIGEN_CANONICO:
            return await _cerrar_canonico_de_lista(conexion, trabajo_id)
        if publicar_directo or autopublicar():
            await _pasar_a(conexion, trabajo_id, EstadoTrabajo.PUBLICADO.value, terminado_en=ahora())
            await _publicar_evento(conexion, trabajo_id)
            return EstadoTrabajo.PUBLICADO.value
        await _pasar_a(conexion, trabajo_id, EstadoTrabajo.ESPERA_REVISION.value)
    return EstadoTrabajo.ESPERA_REVISION.value


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------


async def _procesar_verificado(
    motor: Any,
    trabajo_id: uuid.UUID,
    catalogo: ClienteCatalogo,
    encontradas: list[dict[str, Any]],
    preferencias: dict[str, Any],
    cifrador: Any,
    publicar_directo: bool = False,
) -> str:
    """La ruta rapida: lista(s) ya revisada(s) -> directo a optimizacion.

    No toca Gemini ni `emparejar`: lee `/resueltos` del catalogo, que trae cada
    item con su concepto ya resuelto y los productos candidatos curados. Aun
    asi escribe ITEM+CANDIDATO+RESOLUCION para que el timeline de revision y
    las lecturas de abajo (LINEA referencia ITEM) queden coherentes, y marca
    percepcion/normalizacion/resolucion como OK con `fuente='lista_verificada'`
    —satisfechas por la lista, no saltadas ni fallidas.
    """
    reloj = time.monotonic()
    ids_item: dict[tuple[str, int], uuid.UUID] = {}
    renglones: list[Renglon] = []

    async with motor.engine.begin() as conexion:
        for entrada in encontradas:
            hijo = entrada["hijo"]
            datos = await catalogo.resueltos(str(entrada["version_id"]))
            for item in datos.get("items") or ():
                orden = int(item["orden"])
                item_id = uuid.uuid4()
                ids_item[(hijo, orden)] = item_id

                candidatos = tuple(_candidato(c) for c in (item.get("candidatos") or ()))
                tipo = item.get("tipo_item") or "util"
                modo = item.get("modo_adquisicion") or "mercado_abierto"
                # La misma puerta que la ruta lenta (`busca_en_catalogo`): solo lo
                # que se compra en el catalogo lleva resolucion con producto. Lo
                # demas (no_comprar, uniforme, licencia, edicion exclusiva) es una
                # linea informativa sin resolucion, como alla.
                surtible = (
                    item.get("concepto_codigo") is not None
                    and tipo in BUSCA_EN_CATALOGO
                    and modo in {"mercado_abierto", "libro_libre"}
                )
                estado = EstadoResolucion.RESUELTO_AUTO.value
                if surtible and not candidatos:
                    # Un util curado cuyo concepto todavia no tiene productos (un
                    # concepto recien creado). Resolverlo sin producto violaba
                    # `resolucion_resuelta_tiene_candidato` y tumbaba el trabajo
                    # entero; es un hueco del catalogo y asi se marca.
                    estado = EstadoResolucion.HUECO_CATALOGO.value
                elif not surtible and tipo == "texto" and modo in {"mercado_abierto", "libro_libre"}:
                    estado = EstadoResolucion.SIN_MATCH.value

                await conexion.execute(
                    insert(ITEM).values(
                        id=item_id,
                        trabajo_id=trabajo_id,
                        hijo_referencia=hijo,
                        orden=orden,
                        texto=item["texto_original"],
                        cantidad=int(item.get("cantidad") or 1),
                        unidad_base=(candidatos[0].unidad_base if candidatos else "unidad"),
                        tipo_item=tipo,
                        modo_adquisicion=modo,
                        instruccion_colegio=item.get("instruccion_colegio"),
                        url_externa=item.get("url_externa"),
                        nota=None,
                    )
                )

                if surtible:
                    elegido_id: uuid.UUID | None = None
                    for orden_c, candidato in enumerate(candidatos):
                        candidato_id = uuid.uuid4()
                        if orden_c == 0:
                            elegido_id = candidato_id
                        await conexion.execute(
                            insert(CANDIDATO).values(
                                id=candidato_id,
                                item_crudo_id=item_id,
                                producto_canonico_id=(
                                    uuid.UUID(candidato.producto_id) if candidato.producto_id else None
                                ),
                                sku=candidato.sku,
                                nombre=candidato.nombre,
                                marca=candidato.marca,
                                nivel=candidato.nivel,
                                personaje=candidato.personaje,
                                imagen_url=candidato.imagen_url,
                                unidad_base=candidato.unidad_base,
                                unidades_por_empaque=candidato.unidades_por_empaque,
                                atributos=dict(candidato.atributos),
                                precio_cop=candidato.precio_cop,
                                confianza=1.0,
                                cumple_atributos=candidato.cumple,
                                orden=orden_c,
                            )
                        )

                    # Lo que el renglon exige lo decide el catalogo (`/resueltos`
                    # filtra los candidatos por los atributos del renglon). Aqui se
                    # guarda para que el hueco diga que se pidio y no parezca un
                    # concepto vacio.
                    impuestos = dict(item.get("atributos_impuestos") or {})
                    por_revisar = list(item.get("atributos_por_revisar") or ())
                    pedido = ", ".join(f"{k}={v}" for k, v in impuestos.items())
                    if candidatos:
                        motivo = "resuelto desde lista verificada"
                    elif impuestos:
                        motivo = f"lista verificada: ningun producto cumple {pedido}"
                    else:
                        motivo = "lista verificada: el concepto aun no tiene productos"
                    if por_revisar:
                        motivo += f"; revisar: {', '.join(por_revisar)} (el renglon nombra varios valores)"
                    if item.get("posible_repetido_de") is not None:
                        motivo += f"; posible repetido de la linea {item['posible_repetido_de']}"
                    resolucion_id = uuid.uuid4()
                    await conexion.execute(
                        insert(RESOLUCION).values(
                            id=resolucion_id,
                            item_crudo_id=item_id,
                            estado=estado,
                            concepto_codigo=item.get("concepto_codigo"),
                            concepto_nombre=item.get("concepto_nombre"),
                            parecido=1.0,
                            candidato_item_id=elegido_id,
                            atributos_impuestos=impuestos,
                            motivo=motivo,
                        )
                    )
                    await conexion.execute(
                        insert(TRANSICION).values(
                            id=uuid.uuid4(),
                            resolucion_item_id=resolucion_id,
                            estado_anterior=None,
                            estado_nuevo=estado,
                            motivo=motivo,
                        )
                    )

                renglones.append(
                    Renglon(
                        hijo=hijo,
                        orden=orden,
                        texto=item["texto_original"],
                        tipo_item=tipo,
                        modo_adquisicion=modo,
                        cantidad=int(item.get("cantidad") or 1),
                        estado_resolucion=estado,
                        unidad_base=(candidatos[0].unidad_base if candidatos else "unidad"),
                        concepto_codigo=item.get("concepto_codigo"),
                        concepto_nombre=item.get("concepto_nombre"),
                        parecido=1.0,
                        candidatos=candidatos,
                        # Lo que no se surte dice por que y que hacer, igual que
                        # en la ruta lenta; antes salia mudo, como un faltante.
                        mensaje=(
                            None
                            if surtible
                            else _mensaje_por_tipo(item["texto_original"], tipo, modo) or None
                        ),
                        instruccion_colegio=item.get("instruccion_colegio"),
                        url_externa=item.get("url_externa"),
                        nota=None,
                        uno_por_estudiante=bool(item.get("uno_por_estudiante")),
                    )
                )

        ms = int((time.monotonic() - reloj) * 1000)
        fuente = {"fuente": "lista_verificada"}
        listas_detalle = {
            "fuente": "lista_verificada",
            "listas": [{"hijo": e["hijo"], "version_id": str(e["version_id"])} for e in encontradas],
        }
        await _marcar_etapa(
            conexion, trabajo_id, "percepcion", EstadoEtapa.OK.value, ms=ms, detalle=listas_detalle
        )
        await _marcar_etapa(
            conexion,
            trabajo_id,
            "normalizacion",
            EstadoEtapa.OK.value,
            ms=0,
            detalle={**fuente, "renglones": len(renglones)},
        )
        resueltos = sum(1 for r in renglones if r.concepto_codigo is not None)
        await _marcar_etapa(
            conexion,
            trabajo_id,
            "resolucion",
            EstadoEtapa.OK.value,
            ms=0,
            detalle={**fuente, "resueltos": resueltos, "a_revision": 0},
        )

    # El producto de personaje de las anclas es I/O de red: se resuelve FUERA
    # de la transaccion de escritura (misma consulta que el interruptor del Fan).
    swaps = await _anclas_de_personaje(catalogo, _personaje_pedido(preferencias))

    reloj = time.monotonic()
    kits = armar_los_tres(renglones, preferencias)
    kits = inyectar_personaje_fan(kits, swaps, preferencias)
    kits = _anclar_kits(kits, preferencias)
    ms = int((time.monotonic() - reloj) * 1000)

    async with motor.engine.begin() as conexion:
        await _escribir_kits(conexion, trabajo_id, kits, ids_item, preferencias, cifrador, ms=ms)

    return await _finalizar(motor, trabajo_id, publicar_directo=publicar_directo)


async def procesar(motor: Any, trabajo_id: uuid.UUID, *, catalogo: ClienteCatalogo | None = None) -> str:
    """Corre las cuatro etapas y deja el trabajo listo para revision.

    Devuelve el estado final. No levanta excepciones hacia arriba salvo que
    el trabajo no exista: un fallo de dependencia se traduce a `fallido` con
    diagnostico, que es lo que la seccion 8 del contrato pide.
    """
    catalogo = catalogo or ClienteCatalogo()
    umbral = tau()
    cifrador = cifrador_desde_entorno()

    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(
                    TRABAJO.c.estado,
                    TRABAJO.c.hijos,
                    TRABAJO.c.preferencias_cifradas,
                    TRABAJO.c.origen,
                ).where(TRABAJO.c.id == trabajo_id)
            )
        ).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(str(trabajo_id))
        if fila.estado == EstadoTrabajo.FALLIDO.value:
            await conexion.execute(
                update(TRABAJO)
                .where(TRABAJO.c.id == trabajo_id)
                .values(estado=EstadoTrabajo.ENCOLADO.value, error=None, mensaje=None)
            )
        hijos = list(fila.hijos or ())
        preferencias = cifrador.descifrar_json(fila.preferencias_cifradas) or {}
        # El kit de una lista que un admin ya aprobo se publica directo y avisa
        # al padre: la revision humana fue sobre la lista, no sobre el kit.
        publicar_directo = fila.origen == "lista_verificada"

    async with motor.engine.begin() as conexion:
        # Idempotente en el claim: el trabajador durable (ADR 0024) ya movio la
        # fila a PROCESANDO bajo SKIP LOCKED antes de llamar aqui, y PROCESANDO
        # no transiciona a si mismo. Solo se transiciona si aun venia ENCOLADO
        # (la llamada directa de las pruebas y el reintento desde FALLIDO, que
        # arriba se reencolo). Retomar un trabajo ya PROCESANDO tras un crash
        # entra por aca sin volver a transicionar.
        if fila.estado != EstadoTrabajo.PROCESANDO.value:
            await _pasar_a(conexion, trabajo_id, EstadoTrabajo.PROCESANDO.value)
        # Reprocesar borra lo anterior. Sin esto, un reintento duplicaria
        # items y kits, y la unica senal seria que el total del kit se
        # duplico: un defecto que solo se ve sumando a mano.
        await conexion.execute(delete(ITEM).where(ITEM.c.trabajo_id == trabajo_id))
        await conexion.execute(delete(KIT).where(KIT.c.trabajo_id == trabajo_id))

    try:
        # --- ruta rapida: lista(s) ya verificada(s) -------------------------
        # Si TODAS las listas apuntadas estan revisadas (revisada_en != null en
        # el catalogo), no hay nada que volver a percibir/normalizar/resolver:
        # el concepto y los candidatos curados ya existen. Se salta directo a
        # optimizacion leyendo `/resueltos` (NO `emparejar`, NO Gemini). Si
        # algun hijo apunta a una lista sin revisar, se usa la ruta lenta para
        # TODO el trabajo: mezclar rutas por hijo abriria un camino sin la
        # revision que la lista verificada ya garantiza, y la correccion pesa
        # mas que ahorrar la percepcion en el hijo verificado.
        encontradas, _sin_lista = await _listas_por_hijo(catalogo, hijos)
        if encontradas and all(e["revisada"] for e in encontradas):
            return await _procesar_verificado(
                motor, trabajo_id, catalogo, encontradas, preferencias, cifrador, publicar_directo
            )

        # --- percepcion -----------------------------------------------------
        reloj = time.monotonic()
        crudos, detalle = await _renglones_de_listas(catalogo, hijos)
        ms = int((time.monotonic() - reloj) * 1000)
        async with motor.engine.begin() as conexion:
            await _marcar_etapa(
                conexion,
                trabajo_id,
                "percepcion",
                EstadoEtapa.DEGRADADA.value if detalle["sin_lista"] else EstadoEtapa.OK.value,
                ms=ms,
                detalle=detalle,
            )

        if not crudos:
            async with motor.engine.begin() as conexion:
                await conexion.execute(
                    update(TRABAJO)
                    .where(TRABAJO.c.id == trabajo_id)
                    .values(
                        estado=EstadoTrabajo.FALLIDO.value,
                        error="sin_lista_oficial",
                        mensaje=(
                            "No encontramos la lista oficial publicada para ese colegio y grado. "
                            "Sube el archivo de la lista o escoge otro grado."
                        ),
                        terminado_en=ahora(),
                    )
                )
            return EstadoTrabajo.FALLIDO.value

        # --- normalizacion --------------------------------------------------
        reloj = time.monotonic()
        normalizados = _normalizar(crudos)
        ms = int((time.monotonic() - reloj) * 1000)
        async with motor.engine.begin() as conexion:
            ids_item = {}
            for renglon in normalizados:
                item_id = uuid.uuid4()
                ids_item[(renglon["hijo"], renglon["orden"])] = item_id
                await conexion.execute(
                    insert(ITEM).values(
                        id=item_id,
                        trabajo_id=trabajo_id,
                        hijo_referencia=renglon["hijo"],
                        orden=renglon["orden"],
                        texto=renglon["texto"],
                        cantidad=renglon["cantidad"],
                        unidad_base=renglon["unidad_base"],
                        tipo_item=renglon["tipo_item"],
                        modo_adquisicion=renglon["modo_adquisicion"],
                        instruccion_colegio=renglon.get("instruccion_colegio"),
                        url_externa=renglon.get("url_externa"),
                        nota=renglon.get("nota"),
                    )
                )
            await _marcar_etapa(
                conexion,
                trabajo_id,
                "normalizacion",
                EstadoEtapa.OK.value,
                ms=ms,
                detalle={"renglones": len(normalizados)},
            )

        # --- resolucion -----------------------------------------------------
        reloj = time.monotonic()
        buscables = [r for r in normalizados if r["busca_en_catalogo"]]
        emparejados: dict[tuple[str, int], dict[str, Any]] = {}
        if buscables:
            respuestas = await catalogo.emparejar(
                [r["texto"] for r in buscables], conceptos=[r.get("concepto_lista") for r in buscables]
            )
            for renglon, respuesta in zip(buscables, respuestas, strict=False):
                if _tipo_del_concepto_manda(renglon, respuesta):
                    continue
                emparejados[(renglon["hijo"], renglon["orden"])] = respuesta
        ms = int((time.monotonic() - reloj) * 1000)

        async with motor.engine.begin() as conexion:
            for clave, respuesta in emparejados.items():
                item_id = ids_item[clave]
                estado = estado_desde_emparejamiento(respuesta, umbral)
                elegido_id: uuid.UUID | None = None
                for orden, opcion in enumerate(respuesta.get("opciones") or ()):
                    candidato_id = uuid.uuid4()
                    if orden == 0:
                        elegido_id = candidato_id
                    await conexion.execute(
                        insert(CANDIDATO).values(
                            id=candidato_id,
                            item_crudo_id=item_id,
                            producto_canonico_id=(
                                uuid.UUID(opcion["producto_id"]) if opcion.get("producto_id") else None
                            ),
                            sku=opcion.get("sku") or "",
                            nombre=opcion.get("nombre") or "",
                            marca=opcion.get("marca"),
                            nivel=opcion.get("nivel") or "confiable",
                            personaje=opcion.get("personaje"),
                            imagen_url=opcion.get("imagen_url"),
                            unidad_base=opcion.get("unidad_base") or "unidad",
                            unidades_por_empaque=int(opcion.get("unidades_por_empaque") or 1),
                            atributos=dict(opcion.get("atributos") or {}),
                            precio_cop=opcion.get("precio_cop"),
                            confianza=float(respuesta.get("parecido") or 0.0),
                            cumple_atributos=bool(opcion.get("cumple", True)),
                            orden=orden,
                        )
                    )
                if estado != EstadoResolucion.RESUELTO_AUTO.value:
                    elegido_id = None

                resolucion_id = uuid.uuid4()
                await conexion.execute(
                    insert(RESOLUCION).values(
                        id=resolucion_id,
                        item_crudo_id=item_id,
                        estado=estado,
                        concepto_codigo=respuesta.get("concepto_codigo"),
                        concepto_nombre=respuesta.get("concepto_nombre"),
                        parecido=float(respuesta.get("parecido") or 0.0),
                        candidato_item_id=elegido_id,
                        atributos_impuestos=dict(respuesta.get("atributos_impuestos") or {}),
                        motivo=respuesta.get("motivo") or None,
                    )
                )
                await conexion.execute(
                    insert(TRANSICION).values(
                        id=uuid.uuid4(),
                        resolucion_item_id=resolucion_id,
                        estado_anterior=None,
                        estado_nuevo=estado,
                        motivo="resolucion automatica del pipeline",
                    )
                )

            pendientes = sum(
                1
                for respuesta in emparejados.values()
                if estado_desde_emparejamiento(respuesta, umbral) != EstadoResolucion.RESUELTO_AUTO.value
            )
            await _marcar_etapa(
                conexion,
                trabajo_id,
                "resolucion",
                EstadoEtapa.OK.value,
                ms=ms,
                detalle={"emparejados": len(emparejados), "a_revision": pendientes},
            )

        # --- optimizacion ---------------------------------------------------
        reloj = time.monotonic()
        renglones = []
        for renglon in normalizados:
            clave = (renglon["hijo"], renglon["orden"])
            respuesta = emparejados.get(clave)
            if respuesta is None:
                # No se busco en catalogo. La linea existe igual: o es
                # informativa (y lleva la instruccion del colegio) o es un
                # texto escolar cuya edicion todavia no resolvemos, y en los
                # dos casos ocultarla dejaria al acudiente con un hueco que
                # descubre tarde.
                estado = EstadoResolucion.RESUELTO_AUTO.value
                candidatos: tuple[Candidato, ...] = ()
                if renglon["tipo_item"] == "texto" and renglon["modo_adquisicion"] in {
                    "mercado_abierto",
                    "libro_libre",
                }:
                    estado = EstadoResolucion.SIN_MATCH.value
            else:
                estado = estado_desde_emparejamiento(respuesta, umbral)
                candidatos = tuple(_candidato(o) for o in (respuesta.get("opciones") or ()))

            renglones.append(
                Renglon(
                    hijo=renglon["hijo"],
                    orden=renglon["orden"],
                    texto=renglon["texto"],
                    tipo_item=renglon["tipo_item"],
                    modo_adquisicion=renglon["modo_adquisicion"],
                    cantidad=renglon["cantidad"],
                    estado_resolucion=estado,
                    unidad_base=renglon["unidad_base"],
                    concepto_codigo=(respuesta or {}).get("concepto_codigo"),
                    concepto_nombre=(respuesta or {}).get("concepto_nombre"),
                    parecido=float((respuesta or {}).get("parecido") or 0.0),
                    candidatos=candidatos,
                    mensaje=(respuesta or {}).get("motivo") or renglon.get("mensaje") or None,
                    instruccion_colegio=renglon.get("instruccion_colegio"),
                    url_externa=renglon.get("url_externa"),
                    nota=renglon.get("nota"),
                )
            )

        swaps = await _anclas_de_personaje(catalogo, _personaje_pedido(preferencias))
        kits = armar_los_tres(renglones, preferencias)
        kits = inyectar_personaje_fan(kits, swaps, preferencias)
        kits = _anclar_kits(kits, preferencias)
        ms = int((time.monotonic() - reloj) * 1000)

        async with motor.engine.begin() as conexion:
            await _escribir_kits(conexion, trabajo_id, kits, ids_item, preferencias, cifrador, ms=ms)

        return await _finalizar(motor, trabajo_id, publicar_directo=publicar_directo)

    except RemotoCaido as error:
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(TRABAJO)
                .where(TRABAJO.c.id == trabajo_id)
                .values(
                    estado=EstadoTrabajo.FALLIDO.value,
                    error="dependencia_caida",
                    mensaje=(
                        f"El servicio de {error.servicio} no respondio ({error.detalle}). "
                        "El trabajo quedo guardado y se puede reintentar."
                    ),
                    terminado_en=ahora(),
                )
            )
        return EstadoTrabajo.FALLIDO.value
    except Exception as error:  # noqa: BLE001 - el trabajo no puede quedar colgado
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(TRABAJO)
                .where(TRABAJO.c.id == trabajo_id)
                .values(
                    estado=EstadoTrabajo.FALLIDO.value,
                    error="error_interno",
                    mensaje=f"El pipeline fallo: {error}",
                    terminado_en=ahora(),
                )
            )
        return EstadoTrabajo.FALLIDO.value


async def lanzar(motor: Any, trabajo_id: uuid.UUID) -> None:
    """Encola el trabajo; el trabajador durable lo procesa (ADR 0024).

    Ya NO arranca una `asyncio.Task` en el proceso del API —esa era la unica
    parte del sistema donde una caida de proceso perdia trabajo del usuario, y su
    propio docstring lo admitia—. Solo garantiza que el trabajo quede `encolado`
    (transaccional, durable): `tukit_inteligencia.trabajador` lo toma con SKIP
    LOCKED, lo mueve a `procesando` y corre `procesar`. La respuesta HTTP al
    acudiente sigue siendo inmediata (202 + `consultar_en`).

    Idempotente: un trabajo ya `encolado` (recien creado) no transiciona; uno
    `fallido` (reintentar) o `en revision` devuelto se reencola para que el worker
    lo retome. Un `procesando`/`publicado` no se puede reencolar (lo frena la
    maquina de estados), que es justo lo que se quiere.

    Con RabbitMQ, el paso a `encolado` deja su aviso en la bandeja, en la misma
    transaccion; uno que ya estaba `encolado` tiene el suyo desde `crear`.
    """
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if actual != EstadoTrabajo.ENCOLADO.value:
            await _pasar_a(conexion, trabajo_id, EstadoTrabajo.ENCOLADO.value)
            await _avisar_encolado(conexion, trabajo_id)


async def _avisar_encolado(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Con RabbitMQ, el aviso de que el trabajo quedo `encolado` (ADR 0046).

    Sin broker nadie lo lee, porque el trabajador sondea la tabla: escribirlo
    solo cambiaria lo que hay en la bandeja.
    """
    if url_broker():
        await RepoTrabajos(conexion).avisar_encolado(trabajo_id)


async def _publicar_evento(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Deja `kits_publicados` en la bandeja, en la MISMA transaccion.

    Delegado a `RepoTrabajos.emitir_evento`, que NO abre transaccion: quien lo
    llama (`_finalizar`, `revisar`) lo hace dentro del mismo `async with` que el
    paso a PUBLICADO, para que el evento no sobreviva a un rollback (no dual-write).
    """
    await RepoTrabajos(conexion).emitir_evento(trabajo_id)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def _linea_publica(fila: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "item_id": str(fila.item_crudo_id),
        "hijo": fila.hijo_referencia,
        "orden": int(fila.orden),
        "descripcion": fila.descripcion,
        "tipo": fila.tipo,
        "estado_resolucion": fila.estado_resolucion,
        "cantidad_pedida": int(fila.cantidad_pedida),
        "unidad_base": fila.unidad_base,
        "unidades_por_empaque": int(fila.unidades_por_empaque),
        "unidades_a_comprar": int(fila.unidades_a_comprar),
        "informativa": bool(fila.informativa),
        "subtotal_linea": fila.subtotal_cop,
        "mensaje": fila.mensaje,
    }
    # El codigo del concepto (`C001`) sale de RESOLUCION, no de LINEA: es la
    # llave con la que la matriz agrupa y con la que el interruptor de personaje
    # del Fan encuentra sus anclas. `getattr` porque los otros llamadores de
    # `_linea_publica` pasan una fila de solo-LINEA sin el join.
    concepto = getattr(fila, "concepto_codigo", None)
    if concepto:
        cuerpo["concepto"] = concepto
    if fila.instruccion_colegio:
        cuerpo["instruccion_colegio"] = fila.instruccion_colegio
    if fila.url_externa:
        cuerpo["url_externa"] = fila.url_externa
    if fila.no_consolidable:
        cuerpo["no_consolidable"] = True
        cuerpo["motivo_no_consolidable"] = fila.motivo_no_consolidable
    if fila.sku:
        cuerpo["producto_elegido"] = {
            "sku": fila.sku,
            "nombre": fila.nombre_producto,
            "marca": fila.marca,
            "nivel": fila.nivel,
            "personaje": fila.personaje,
            "imagen_url": fila.imagen_url,
            "precio": fila.precio_unitario_cop,
        }
    cuerpo["alternativas"] = list(fila.alternativas or ())
    return cuerpo


async def ver(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    incluir_kits: bool | None = None,
    incluir_admin: bool = False,
    catalogo: ClienteCatalogo | None = None,
) -> dict[str, Any]:
    """El cuerpo de `GET /v1/trabajos/{id}`.

    Mientras el estado no sea `publicado`, `kits` va vacio: el acudiente
    nunca ve un kit sin revisar, y esa es la razon de ser de
    `espera_revision`. Admin usa el mismo lector con `incluir_kits=True`,
    porque su trabajo es justamente mirar lo que todavia no se publica.

    Un trabajo `parent_apply` NO tiene kits propios: es un puntero al canonico
    (modelo por referencia). Sus kits se resuelven al vuelo siguiendo
    `hijos[0].canonico_trabajo_id` + su perfil, con el personaje aplicado sobre
    las anclas. Por eso `ver` acepta `catalogo`: sin el, el swap de personaje no
    se puede hacer y el kit sale con sus productos neutrales.

    `incluir_admin` agrega los campos que solo la consola interna ve
    (`recibido_en`, `contacto_id`, `lineas_pendientes`). El acudiente nunca
    los recibe: `contacto_id` reintroduciria a mano la referencia que la
    notificacion resuelve al vuelo, y esa asimetria es intencional.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        if cabeza is None:
            raise TrabajoNoExiste(str(trabajo_id))

        etapas = [
            {
                "nombre": f.nombre,
                "estado": f.estado,
                "ms": f.ms,
                "detalle": dict(f.detalle or {}),
            }
            for f in await conexion.execute(select(ETAPA).where(ETAPA.c.trabajo_id == trabajo_id))
        ]
        etapas.sort(key=lambda e: ETAPAS.index(e["nombre"]) if e["nombre"] in ETAPAS else 99)

        mostrar = incluir_kits if incluir_kits is not None else cabeza.estado == EstadoTrabajo.PUBLICADO.value
        kits: list[dict[str, Any]] = []
        recomendado: dict[str, Any] | None = None
        # Lo que el acudiente cambio en sus kits: se aplica al leer, nunca se
        # escribe en `linea_kit` (ver `TrabajoPipeline.cambios`).
        cambios: dict[str, Any] = dict(cabeza.cambios or {})

        if mostrar and cabeza.origen == "parent_apply":
            # Un puntero al canonico: no tiene kits propios. Se sigue
            # `hijos[0].canonico_trabajo_id` y se pintan los TRES kits del
            # canonico, con el personaje aplicado sobre las anclas: el que eligio
            # al empezar va marcado, y si prefiere otro puede pagar ese.
            hijo = (list(cabeza.hijos or ()) or [{}])[0]
            canonico_id = hijo.get("canonico_trabajo_id")
            perfil = str(hijo.get("perfil") or "")
            if canonico_id and perfil:
                # ponytail: 4 llamadas de catalogo dentro de la txn de lectura
                # (SELECT puro, sin locks). Si molesta, resolver los swaps antes
                # de abrir la txn con una pre-lectura de cabeza.
                personaje = hijo.get("personaje")
                swaps = await _anclas_de_personaje(catalogo, personaje) if catalogo else {}
                # Los canonicos traen Ahorrador y Premium (ADR 0030); uno viejo
                # puede traer tambien un Fan, que ya no se muestra: el Fan es del
                # acudiente que pidio un personaje, y se arma para el.
                canonicos = [
                    p
                    for p in (
                        await conexion.execute(
                            select(KIT.c.perfil)
                            .where(KIT.c.trabajo_id == uuid.UUID(str(canonico_id)))
                            .order_by(KIT.c.total_cop)
                        )
                    ).scalars()
                    if p != PerfilKit.FAN.value
                ]
                perfiles = list(canonicos)
                if personaje and PerfilKit.AHORRADOR.value in canonicos:
                    perfiles.insert(canonicos.index(PerfilKit.AHORRADOR.value) + 1, PerfilKit.FAN.value)
                for perfil_kit in perfiles:
                    # El Fan es el Ahorrador canonico con el personaje en las
                    # anclas; los demas se pintan tal cual los reviso una persona.
                    base, swaps_kit = (
                        (PerfilKit.AHORRADOR.value, swaps)
                        if perfil_kit == PerfilKit.FAN.value
                        else (perfil_kit, {})
                    )
                    lineas, total = await _lineas_aplicadas(
                        conexion, uuid.UUID(str(canonico_id)), base, swaps_kit
                    )
                    if cambios.get(perfil_kit):
                        lineas, total = _aplicar_cambios(lineas, cambios[perfil_kit])
                    kits.append(
                        {
                            "perfil": perfil_kit,
                            "total": total,
                            "objetivos": _objetivos_de_lineas(lineas, total),
                            "lineas": lineas,
                            "consolidaciones": [],
                            "informativas": sum(1 for linea in lineas if linea["informativa"]),
                        }
                    )
                recomendado = {
                    "perfil": perfil,
                    "razon": (
                        "Es el kit que elegiste al empezar. Puedes mirar los otros y cambiarte si prefieres."
                    ),
                    "dentro_de_presupuesto": None,
                }
        elif mostrar:
            for kit in await conexion.execute(
                select(KIT).where(KIT.c.trabajo_id == trabajo_id).order_by(KIT.c.total_cop)
            ):
                lineas = [
                    _linea_publica(f)
                    for f in await conexion.execute(
                        select(LINEA, RESOLUCION.c.concepto_codigo)
                        .select_from(
                            LINEA.join(
                                RESOLUCION,
                                RESOLUCION.c.item_crudo_id == LINEA.c.item_crudo_id,
                                isouter=True,
                            )
                        )
                        .where(LINEA.c.kit_id == kit.id)
                        .order_by(LINEA.c.hijo_referencia, LINEA.c.orden)
                    )
                ]
                total = int(kit.total_cop)
                objetivos = dict(kit.objetivos or {})
                if cambios.get(kit.perfil):
                    lineas, total = _aplicar_cambios(lineas, cambios[kit.perfil])
                    objetivos = _objetivos_de_lineas(lineas, total)
                cuerpo = {
                    "perfil": kit.perfil,
                    "total": total,
                    "objetivos": objetivos,
                    "lineas": lineas,
                    "consolidaciones": list(kit.consolidaciones or ()),
                    "informativas": sum(1 for linea in lineas if linea["informativa"]),
                }
                kits.append(cuerpo)
                if kit.recomendado:
                    recomendado = {
                        "perfil": kit.perfil,
                        "razon": kit.razon_recomendacion,
                        "dentro_de_presupuesto": kit.dentro_de_presupuesto,
                    }

        campos_admin: dict[str, Any] = {}
        if incluir_admin:
            # Los item_id que todavia esperan a una persona: los que la
            # resolucion no dejo en RESUELTO_AUTO. Es el mismo criterio que
            # `cola()`, pero devolviendo los ids de este trabajo en vez de un
            # conteo, porque la consola los necesita uno a uno.
            pendientes = await conexion.execute(
                select(ITEM.c.id)
                .select_from(ITEM.join(RESOLUCION, RESOLUCION.c.item_crudo_id == ITEM.c.id))
                .where(
                    ITEM.c.trabajo_id == trabajo_id,
                    RESOLUCION.c.estado != EstadoResolucion.RESUELTO_AUTO.value,
                )
                .order_by(ITEM.c.orden)
            )
            campos_admin = {
                "recibido_en": cabeza.creado_en.isoformat() if cabeza.creado_en else None,
                # Nunca el correo ni el celular: la consola referencia al
                # acudiente por identificador y `operacion` lo resuelve al
                # enviar. Un trabajo de preview o anonimo no tiene usuario.
                "contacto_id": str(cabeza.usuario_id) if cabeza.usuario_id else "",
                "lineas_pendientes": [str(f.id) for f in pendientes],
            }

    return {
        "trabajo_id": str(cabeza.id),
        "estado": cabeza.estado,
        "origen": cabeza.origen,
        "hijos": list(cabeza.hijos or ()),
        "etapas": etapas,
        "kits": kits,
        "recomendado": recomendado,
        "cambios": cambios,
        "degradaciones": list(cabeza.degradaciones or ()),
        "error": cabeza.error,
        "mensaje": cabeza.mensaje,
        "creado_en": cabeza.creado_en.isoformat() if cabeza.creado_en else None,
        "terminado_en": cabeza.terminado_en.isoformat() if cabeza.terminado_en else None,
        "nota_revision": cabeza.nota_revision,
        **campos_admin,
    }


async def ordenar(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    portador: uuid.UUID | None = None,
    perfil: str,
    entrega: dict[str, str],
    correo: str,
    metodo: str = "pse",
    url_redireccion: str | None = None,
    comercio: ClienteComercio,
    catalogo: ClienteCatalogo,
    identidad: ClienteIdentidad | None = None,
) -> dict[str, Any]:
    """El checkout del acudiente: del trabajo publicado a la orden y el pago.

    El navegador manda `trabajo_id` + perfil + direccion + correo, nada mas.
    Aqui se lee el kit de ese perfil (por `ver`, que ya sabe seguir el puntero
    de un `parent_apply` y aplicar el personaje), se arma la orden con SOLO sku
    y precio publico —el id canonico lo resuelve Comercio— y se manda a Comercio
    a congelar y cobrar. Asi ningun id de base sale a la superficie (RPO cero).

    El `usuario_id` sale del trabajo. Un trabajo anonimo (la ruta rapida de
    `/empezar` no exige login) no lo tiene: se registra el contacto con el correo
    del pago, igual que en `crear`. Sin `usuario_id` Comercio no cierra la orden,
    asi que aqui no se degrada: sin destinatario no hay a quien cobrarle.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        if cabeza is None:
            raise TrabajoNoExiste(str(trabajo_id))
        usuario_id = cabeza.usuario_id
        hijos = list(cabeza.hijos or ())
    # Un trabajo con dueno solo lo paga su dueno (`portador` es la sesion de
    # quien llama): el id del trabajo viaja en enlaces y no es un secreto.
    if usuario_id is not None and usuario_id != portador:
        raise CambioNoPermitido(
            "solicitud_ajena", "Inicia sesión con la cuenta que hizo esta solicitud para pagarla.", 403
        )

    if usuario_id is None:
        cliente = identidad or ClienteIdentidad()
        crudo = await cliente.registrar_contacto(correo)
        if not crudo:
            raise RemotoCaido("identidad", "no se pudo registrar el contacto para el pago")
        usuario_id = uuid.UUID(crudo)

    vista = await ver(motor, trabajo_id, incluir_kits=True, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    if kit is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}")

    lineas = []
    for linea in kit["lineas"]:
        elegido = linea.get("producto_elegido")
        # Una linea informativa (o sin producto/precio) no se compra: se muestra
        # en el kit pero no entra a la orden. Tampoco la que quedo en cero por
        # ir junto a otra ("Ya va en la linea N", o la de un hermano): Comercio
        # exige cantidad > 0 y una sola en cero tumbaba el checkout entero.
        # Lo que el acudiente descarto ("ya lo tengo") tampoco se cobra.
        if (
            linea["informativa"]
            or linea.get("descartado")
            or not elegido
            or elegido.get("precio") is None
        ):
            continue
        if int(linea["unidades_a_comprar"]) <= 0:
            continue
        lineas.append(
            {
                "sku": elegido["sku"],
                "nombre": elegido["nombre"],
                "cantidad": int(linea["unidades_a_comprar"]),
                "precio_unitario": int(elegido["precio"]),
            }
        )
    if not lineas:
        # El kit del perfil EXISTE, pero ninguna linea tiene producto+precio que
        # Tukit pueda cobrar hoy: no es "no hay kit" (eso es el 404 de arriba),
        # es un kit sin nada comprable. Se distingue para no mentirle al
        # acudiente con "no tiene un kit de ese perfil". `CheckoutRechazado`
        # lleva su propio estado y el router lo reenvia verbatim.
        raise CheckoutRechazado(
            409,
            {
                "error": "kit_sin_lineas",
                "mensaje": "Este kit no tiene productos que Tukit pueda vender hoy.",
            },
        )

    colegios = sorted({h["colegio_id"] for h in hijos if h.get("colegio_id")})
    estado, orden = await comercio.crear_orden(
        {
            "usuario_id": str(usuario_id),
            "trabajo_id": str(trabajo_id),
            "hijos": len(hijos),
            "colegios": colegios,
            "lineas": lineas,
            "entrega": entrega,
        }
    )
    if estado != 201:
        raise CheckoutRechazado(estado, orden)

    estado, pago = await comercio.iniciar_pago(
        orden["pedido_id"],
        {"correo_cliente": correo, "metodo": metodo, "url_redireccion": url_redireccion},
    )
    if estado != 201:
        raise CheckoutRechazado(estado, pago)

    return {"pedido_id": orden["pedido_id"], "total": orden["total"], **pago}


# ---------------------------------------------------------------------------
# Revision humana
# ---------------------------------------------------------------------------


async def cola(motor: Any, *, pagina: int = 1, por_pagina: int = 50) -> dict[str, Any]:
    """Los trabajos esperando a una persona, del mas viejo al mas nuevo.

    El orden es por antiguedad y no por tamano ni por confianza: quien lleva
    mas esperando se atiende primero, que es la unica politica que no deja a
    nadie al final para siempre.
    """
    a_revision = (
        select(ITEM.c.trabajo_id.label("tid"), func.count().label("dudosos"))
        .select_from(ITEM.join(RESOLUCION, RESOLUCION.c.item_crudo_id == ITEM.c.id))
        .where(RESOLUCION.c.estado != EstadoResolucion.RESUELTO_AUTO.value)
        .group_by(ITEM.c.trabajo_id)
        .subquery()
    )
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.origen,
            TRABAJO.c.creado_en,
            TRABAJO.c.hijos,
            func.coalesce(a_revision.c.dudosos, 0).label("dudosos"),
        )
        .select_from(TRABAJO.outerjoin(a_revision, a_revision.c.tid == TRABAJO.c.id))
        .where(TRABAJO.c.estado == EstadoTrabajo.ESPERA_REVISION.value)
        .order_by(TRABAJO.c.creado_en)
    )

    async with motor.engine.begin() as conexion:
        total = int(await conexion.scalar(select(func.count()).select_from(consulta.subquery())) or 0)
        filas = await conexion.execute(consulta.limit(por_pagina).offset((pagina - 1) * por_pagina))
        datos = [
            {
                "trabajo_id": str(f.id),
                "estado": f.estado,
                "creado_en": f.creado_en.isoformat() if f.creado_en else None,
                "origen": f.origen,
                "hijos": len(list(f.hijos or ())),
                # Lo que el trabajo ya sabe de sus hijos. El nombre del colegio
                # no: ese lo pone quien lee, con el directorio que ya tiene.
                "colegios": sorted({h["colegio_id"] for h in f.hijos or () if h.get("colegio_id")}),
                "grados": list(dict.fromkeys(h["grado"] for h in f.hijos or () if h.get("grado"))),
                "lineas_a_revisar": int(f.dudosos),
                # Un borrador de edicion de kits ya publicados: el canonico del
                # que salio. None en todo lo demas.
                "edicion_de": next(iter(f.hijos or ()), {}).get("basado_en"),
            }
            for f in filas
        ]
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "trabajos": datos}


# ---------------------------------------------------------------------------
# Panel del acudiente: "Mis solicitudes"
# ---------------------------------------------------------------------------


def _a_consciente(momento: Any) -> datetime:
    """Un `datetime` con zona para ordenar sin chocar naive contra aware.

    Las fechas propias vuelven naive en SQLite (pruebas) y aware en Postgres;
    las del catalogo llegan como ISO por HTTP. Mezclarlas en un `sort` levanta
    `TypeError`, asi que todo se normaliza a aware (UTC si no trae zona) antes
    de comparar. `None` cae al final (fecha minima)."""
    if momento is None:
        return datetime.min.replace(tzinfo=UTC)
    if isinstance(momento, str):
        momento = datetime.fromisoformat(momento)
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


async def mis_solicitudes(motor: Any, usuario_id: uuid.UUID, *, catalogo: Any) -> dict[str, Any]:
    """Las solicitudes del acudiente —listas subidas + trabajos—, ya unidas.

    Una lista subida (en el catalogo) y el trabajo que engendra al aprobarse
    (aca) son la MISMA solicitud: se unen por el `version_id` que el poller
    dejo en el trabajo. Una lista aprobada con su trabajo sale como una sola
    fila `aprobada`, no como dos.

    El `usuario_id` es SIEMPRE el del portador de la sesion, nunca uno del
    navegador; `listas_por_contacto` se llama con ese mismo id.

    Si el catalogo no responde, no se cae la vista: se devuelven los trabajos y
    `listas_disponibles=False` para que el panel muestre un aviso y aun asi
    liste los trabajos (las filas `recibida` que viven en el catalogo no
    aparecen mientras dure la caida).

    Una lista que se subio con el catalogo caido todavia no esta en el catalogo:
    espera en `importacion_lista` (ADR 0040). Tambien sale como `recibida`, con
    `tarea_id: null` porque aun no hay tarea que cancelar, y deja de salir de
    aqui en cuanto se importa: desde ahi la trae el catalogo.
    """
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.origen,
            TRABAJO.c.hijos,
            TRABAJO.c.creado_en,
        )
        .where(TRABAJO.c.usuario_id == usuario_id, TRABAJO.c.estado != EstadoTrabajo.CANCELADO.value)
        .order_by(TRABAJO.c.creado_en.desc())
    )
    pendientes_consulta = (
        select(IMPORTACION.c.colegio_id, IMPORTACION.c.grado, IMPORTACION.c.carga, IMPORTACION.c.creado_en)
        .where(IMPORTACION.c.contacto_referencia == str(usuario_id), IMPORTACION.c.estado == "pendiente")
        .order_by(IMPORTACION.c.creado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))
        pendientes = list(await conexion.execute(pendientes_consulta))

    # Las listas subidas del contacto. Una caida del catalogo degrada la vista,
    # no la tumba (se marca y se sigue con los trabajos).
    try:
        listas = await catalogo.listas_por_contacto(str(usuario_id))
        listas_disponibles = True
    except RemotoCaido:
        listas = []
        listas_disponibles = False

    # `version_id` -> trabajo, para unir una lista aprobada con el trabajo que
    # engendro. Solo los de `lista_verificada` guardan ese id en `hijos[0]`.
    trabajo_por_version: dict[str, Any] = {}
    for fila in filas:
        if fila.origen == "lista_verificada":
            hijos = list(fila.hijos or ())
            vid = hijos[0].get("version_id") if hijos else None
            if vid:
                trabajo_por_version[str(vid)] = fila

    solicitudes: list[dict[str, Any]] = []
    versiones_unidas: set[str] = set()

    # Una solicitud por lista subida: aprobada (con su trabajo) o recibida.
    for lista_subida in listas:
        vid = lista_subida.get("version_id")
        colegio_id = str(lista_subida.get("colegio_id") or "")
        grado = lista_subida.get("grado") or ""
        colegio_nombre = lista_subida.get("colegio_nombre")
        trabajo_ligado = trabajo_por_version.get(str(vid)) if vid else None
        if lista_subida.get("revisada_en") and trabajo_ligado is not None:
            versiones_unidas.add(str(vid))
            solicitudes.append(
                {
                    "tipo": "aprobada",
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "trabajo_id": str(trabajo_ligado.id),
                    "creado_en": trabajo_ligado.creado_en.isoformat() if trabajo_ligado.creado_en else None,
                    "_orden": _a_consciente(trabajo_ligado.creado_en),
                }
            )
        else:
            # Sin aprobar todavia, o aprobada pero el poller aun no crea el
            # trabajo (se autocorrige en la siguiente carga): es "recibida".
            solicitudes.append(
                {
                    "tipo": "recibida",
                    # Con esto el acudiente la cancela (`cancelar_lista_subida`).
                    "tarea_id": lista_subida.get("tarea_id"),
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "creado_en": lista_subida.get("creada_en"),
                    "_orden": _a_consciente(lista_subida.get("creada_en")),
                }
            )

    # Las listas que esperan aca a que el catalogo vuelva.
    for pendiente in pendientes:
        colegio_datos = (pendiente.carga or {}).get("colegio_datos") or {}
        solicitudes.append(
            {
                "tipo": "recibida",
                "tarea_id": None,
                "colegio_id": pendiente.colegio_id,
                "colegio_nombre": colegio_datos.get("nombre"),
                "grado": pendiente.grado,
                "creado_en": _a_consciente(pendiente.creado_en).isoformat(),
                "_orden": _a_consciente(pendiente.creado_en),
            }
        )

    # Los trabajos que no salieron ya como una lista aprobada.
    for fila in filas:
        vid = None
        if fila.origen == "lista_verificada":
            hijos = list(fila.hijos or ())
            vid = hijos[0].get("version_id") if hijos else None
        if vid and str(vid) in versiones_unidas:
            continue
        primer = (list(fila.hijos or ()) or [{}])[0]
        solicitudes.append(
            {
                "tipo": "trabajo",
                "colegio_id": str(primer.get("colegio_id") or ""),
                "colegio_nombre": None,
                "grado": primer.get("grado") or "",
                "trabajo_id": str(fila.id),
                "estado": fila.estado,
                "creado_en": fila.creado_en.isoformat() if fila.creado_en else None,
                "_orden": _a_consciente(fila.creado_en),
            }
        )

    solicitudes.sort(key=lambda s: s["_orden"], reverse=True)
    for solicitud in solicitudes:
        del solicitud["_orden"]
    return {"solicitudes": solicitudes, "listas_disponibles": listas_disponibles}


# Un pedido cancelado ya no frena la cancelacion de su solicitud. Uno vencido
# sigue en `pendiente_pago` (§9.4): se cancela primero, como cualquier pendiente.
_PEDIDO_SIN_EFECTO = frozenset({"cancelado"})


async def cancelar_solicitud(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    usuario_id: uuid.UUID,
    token: str,
    comercio: ClienteComercio,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """El acudiente cancela una solicitud suya (ADR 0031).

    `token` es la sesion del acudiente: con ella Comercio le dice sus pedidos.

    El trabajo pasa a `cancelado`, terminal, y deja de salir en "Mis
    solicitudes" y en la cola de revision. No se cancela:

    - la solicitud de otro (`solicitud_ajena`, 403);
    - un trabajo que el pipeline esta armando (`en_proceso`): se escribe en
      medio y el resultado quedaria a medias;
    - el trabajo que hoy es el kit canonico de su grado (`kit_canonico`):
      aprobarlo lo fijo como la cache de la que copian los demas acudientes;
    - un kit con un pago pendiente (`pedido_pendiente`): primero se cancela el
      pedido, que es lo que consulta a la pasarela antes de soltarlo (§9.3);
    - un kit ya comprado (`kit_comprado`).

    Si el trabajo salio de una lista que el acudiente subio, la lista tambien se
    le desvincula en el Catalogo; si no, volveria a salir como "recibida". Sin
    Comercio no se cancela a ciegas: `RemotoCaido`.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.usuario_id, TRABAJO.c.origen, TRABAJO.c.hijos).where(
                    TRABAJO.c.id == trabajo_id
                )
            )
        ).one_or_none()
    if cabeza is None:
        raise TrabajoNoExiste(str(trabajo_id))
    if cabeza.usuario_id != usuario_id:
        raise SolicitudNoCancelable("solicitud_ajena", "Esta solicitud no es de tu cuenta.", 403)
    if cabeza.estado == EstadoTrabajo.CANCELADO.value:
        return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.CANCELADO.value}
    if cabeza.estado == EstadoTrabajo.PROCESANDO.value:
        raise SolicitudNoCancelable(
            "en_proceso", "Estamos armando tu kit justo ahora. Intenta cancelarla en un minuto."
        )
    # Aprobar el trabajo de un acudiente lo fija como cache de su grado
    # (`revisar`): la ruta rapida de los demas padres copia de ahi. Cancelarlo
    # dejaria el puntero en un trabajo cancelado, asi que mientras sea el
    # canonico no se toca; se cancela cuando otra publicacion lo reemplace.
    async with motor.engine.begin() as conexion:
        es_canonico = await conexion.scalar(
            select(KIT_CANONICO.c.id).where(KIT_CANONICO.c.trabajo_id == trabajo_id).limit(1)
        )
    if es_canonico is not None:
        raise SolicitudNoCancelable(
            "kit_canonico",
            "Este kit quedó como el kit de referencia de tu colegio y grado, así que no se "
            "cancela. Si no lo necesitas, no tienes que comprarlo.",
        )

    for pedido in await comercio.pedidos_de(token):
        if str(pedido.get("trabajo_id")) != str(trabajo_id) or pedido.get("estado") in _PEDIDO_SIN_EFECTO:
            continue
        if pedido.get("estado") == "pendiente_pago":
            raise SolicitudNoCancelable(
                "pedido_pendiente",
                "Tienes un pedido de este kit esperando pago. Cancélalo primero en Mis pedidos.",
            )
        raise SolicitudNoCancelable(
            "kit_comprado", "Ya compraste este kit, así que la solicitud no se cancela."
        )

    async with motor.engine.begin() as conexion:
        await _pasar_a(conexion, trabajo_id, EstadoTrabajo.CANCELADO.value)

    hijo = (list(cabeza.hijos or ()) or [{}])[0]
    if cabeza.origen == "lista_verificada" and hijo.get("version_id"):
        await catalogo.retirar_de_contacto(str(usuario_id), version_id=str(hijo["version_id"]))
    return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.CANCELADO.value}


async def cancelar_lista_subida(
    usuario_id: uuid.UUID, tarea_id: str, *, catalogo: ClienteCatalogo
) -> dict[str, Any]:
    """El acudiente cancela una lista que subio y que todavia no tiene kit.

    La lista no se borra: es una lista oficial del colegio y alguien la puede
    curar igual. Solo deja de ser suya (no sale en "Mis solicitudes" ni le arma
    un kit al aprobarse). El Catalogo solo desvincula tareas de este contacto.
    """
    retiradas = await catalogo.retirar_de_contacto(str(usuario_id), tarea_id=tarea_id)
    return {"tarea_id": tarea_id, "retiradas": retiradas}


async def eliminar(motor: Any, trabajo_id: uuid.UUID) -> None:
    """Borra un trabajo y todo lo que cuelga de el (cascada de FKs).

    Un trabajo `publicado` esta protegido: es el kit canonico de su colegio y
    grado (o lo alimentara), y borrarlo perderia una revision humana ya
    aprobada. Los demas estados —previews desechables, encolados, fallidos— se
    pueden borrar sin remordimiento. La cascada `ondelete=CASCADE` de etapas,
    items, candidatos, resoluciones, kits y lineas hace el resto; lo unico que
    no cuelga por FK es la `bandeja_salida`, que es el log de eventos y se deja.
    """
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if actual == EstadoTrabajo.PUBLICADO.value:
            raise TrabajoProtegido(actual)
        await conexion.execute(delete(TRABAJO).where(TRABAJO.c.id == trabajo_id))


async def previews_de(motor: Any, colegio_id: str, grado: str, anio_lectivo: int) -> list[uuid.UUID]:
    """Los previews desechables vivos de un (colegio, grado, anio).

    El colegio/grado no son columnas: viven en el JSON `hijos`, tal como los
    mando el admin al previsualizar. Se filtra en memoria (son pocos) los
    trabajos con `origen='preview_onboarding'` que NO estan publicados y cuyo
    primer hijo cuadra. Lo usa `preview_onboarding` para no acumular copias.
    """
    async with motor.engine.begin() as conexion:
        filas = await conexion.execute(
            select(TRABAJO.c.id, TRABAJO.c.hijos).where(
                TRABAJO.c.origen == "preview_onboarding",
                TRABAJO.c.estado != EstadoTrabajo.PUBLICADO.value,
            )
        )
    coincidencias: list[uuid.UUID] = []
    for fila in filas:
        hijo = next(iter(fila.hijos or ()), None)
        if not hijo:
            continue
        if (
            str(hijo.get("colegio_id") or "") == colegio_id
            and str(hijo.get("grado") or "") == grado
            and int(hijo.get("anio_lectivo") or 0) == anio_lectivo
        ):
            coincidencias.append(fila.id)
    return coincidencias


async def _resolucion_de(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> Any:
    return await RepoTrabajos(conexion).resolucion_de(trabajo_id, item_id)


async def _sku_a_validar(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID, actual: Any) -> str | None:
    """El producto que "validar el elegido" confirma cuando no llega `sku`.

    Primero el que la LINEA tiene en el kit recomendado —es el que el admin ve
    marcado como "elegido por el sistema"—, luego el de cualquier otro kit, y
    al final el del candidato que la resolucion ya apuntaba. La LINEA va antes
    que el candidato porque la ruta lenta deja `candidato_item_id` nulo en todo
    lo que no es RESUELTO_AUTO, y el optimizador igual eligio un producto para
    el kit: ese es el que hay que confirmar.
    """
    sku = await conexion.scalar(
        select(LINEA.c.sku)
        .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
        .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id, LINEA.c.sku.is_not(None))
        .order_by(KIT.c.recomendado.desc())
        .limit(1)
    )
    if sku:
        return str(sku)
    if actual.candidato_item_id is not None:
        previo = await conexion.scalar(
            select(CANDIDATO.c.sku).where(CANDIDATO.c.id == actual.candidato_item_id)
        )
        if previo:
            return str(previo)
    return None


async def _candidato_de(conexion: Any, item_id: uuid.UUID, sku: str) -> uuid.UUID | None:
    return await conexion.scalar(
        select(CANDIDATO.c.id).where(and_(CANDIDATO.c.item_crudo_id == item_id, CANDIDATO.c.sku == sku))
    )


async def _linea_con_sku(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID, sku: str) -> Any:
    return (
        await conexion.execute(
            select(LINEA)
            .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
            .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id, LINEA.c.sku == sku)
            .order_by(KIT.c.recomendado.desc())
            .limit(1)
        )
    ).first()


async def _registrar_candidato(
    conexion: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    sku: str,
    producto_catalogo: dict[str, Any] | None,
) -> uuid.UUID | None:
    """El CANDIDATO de (item, sku); si no existe, lo da de alta.

    El producto que una linea muestra no siempre fue candidato del item: el
    interruptor de personaje del Fan y `fijar_producto_en_linea` ponen en la
    LINEA productos que el emparejamiento nunca ofrecio. Validarlo es una
    decision legitima del revisor, y la resolucion exige un candidato
    (CHECK `resolucion_resuelta_tiene_candidato`), asi que se registra uno con
    los datos que ya tiene la LINEA —o, si no hay LINEA con ese sku, con los
    del catalogo—. `confianza=1.0` porque lo confirmo una persona.
    """
    existente = await _candidato_de(conexion, item_id, sku)
    if existente is not None:
        return existente

    linea = await _linea_con_sku(conexion, trabajo_id, item_id, sku)
    if linea is not None:
        datos = {
            "producto_canonico_id": linea.producto_canonico_id,
            "nombre": linea.nombre_producto or sku,
            "marca": linea.marca,
            "nivel": linea.nivel or "confiable",
            "personaje": linea.personaje,
            "imagen_url": linea.imagen_url,
            "unidad_base": linea.unidad_base or "unidad",
            "unidades_por_empaque": int(linea.unidades_por_empaque or 1),
            "precio_cop": linea.precio_unitario_cop,
        }
    elif producto_catalogo is not None:
        datos = {
            "producto_canonico_id": None,
            "nombre": producto_catalogo.get("nombre") or sku,
            "marca": producto_catalogo.get("marca"),
            "nivel": producto_catalogo.get("nivel") or "confiable",
            "personaje": producto_catalogo.get("personaje"),
            "imagen_url": producto_catalogo.get("imagen_url"),
            "unidad_base": producto_catalogo.get("unidad_base") or "unidad",
            "unidades_por_empaque": int(producto_catalogo.get("unidades_por_empaque") or 1),
            "precio_cop": producto_catalogo.get("precio_desde"),
        }
    else:
        return None

    siguiente = await conexion.scalar(
        select(func.coalesce(func.max(CANDIDATO.c.orden), -1) + 1).where(CANDIDATO.c.item_crudo_id == item_id)
    )
    candidato_id = uuid.uuid4()
    await conexion.execute(
        insert(CANDIDATO).values(
            id=candidato_id,
            item_crudo_id=item_id,
            sku=sku,
            atributos={},
            confianza=1.0,
            cumple_atributos=True,
            orden=int(siguiente or 0),
            **datos,
        )
    )
    return candidato_id


async def decidir_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    estado: str,
    sku: str | None = None,
    actor: uuid.UUID | None = None,
    motivo: str | None = None,
    catalogo: ClienteCatalogo | None = None,
) -> dict[str, Any]:
    """AD-04: una persona valida el emparejamiento o lo marca sin coincidencia.

    Escribe la transicion ANTES de cambiar el estado y en la misma
    transaccion, porque una decision humana sin rastro de quien la tomo es
    justo el control sin dueno que la cola existe para no ser.

    Validar (RESUELTO_AUTO) sin `sku` confirma el producto que la linea tiene
    en el kit (`_sku_a_validar`). Si ese producto no es candidato del item se
    registra (`_registrar_candidato`); solo cuando no hay producto por ningun
    lado se rechaza con `SinProductoQueValidar` —antes eso llegaba a la base
    como RESUELTO_AUTO sin candidato y el CHECK lo convertia en un 500—.

    El estado se copia tambien a las LINEA del item en los tres kits: la
    consola clasifica por `linea.estado_resolucion`, y sin esto una linea ya
    validada seguia apareciendo como pendiente.
    """
    resuelto = estado == EstadoResolucion.RESUELTO_AUTO.value

    # El catalogo se consulta FUERA de la transaccion (una llamada HTTP no debe
    # sostener un lock), y solo cuando el sku no esta ni como candidato ni en
    # una LINEA del item: es el caso raro, no el comun.
    producto_catalogo: dict[str, Any] | None = None
    if resuelto and sku and catalogo is not None:
        async with motor.engine.begin() as conexion:
            conocido = await _candidato_de(conexion, item_id, sku) is not None or (
                await _linea_con_sku(conexion, trabajo_id, item_id, sku) is not None
            )
        if not conocido:
            try:
                producto_catalogo = await catalogo.producto(sku)
            except (RemotoCaido, KeyError):
                producto_catalogo = None

    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
        actual = await _resolucion_de(conexion, trabajo_id, item_id)
        if actual is None:
            raise TrabajoNoExiste(f"{trabajo_id}/{item_id}")

        candidato_id: uuid.UUID | None = None
        sku_usado = sku
        if resuelto:
            sku_usado = sku or await _sku_a_validar(conexion, trabajo_id, item_id, actual)
            if sku_usado:
                candidato_id = await _registrar_candidato(
                    conexion, trabajo_id, item_id, sku_usado, producto_catalogo
                )
            if candidato_id is None:
                raise SinProductoQueValidar(sku)

        await conexion.execute(
            insert(TRANSICION).values(
                id=uuid.uuid4(),
                resolucion_item_id=actual.id,
                estado_anterior=actual.estado,
                estado_nuevo=estado,
                motivo=motivo or "decision de Admin Tukit",
                decidida_por=actor,
            )
        )
        await conexion.execute(
            update(RESOLUCION)
            .where(RESOLUCION.c.id == actual.id)
            .values(
                estado=estado,
                candidato_item_id=candidato_id,
                decidido_por=actor,
                decidido_en=ahora(),
            )
        )
        await conexion.execute(
            update(LINEA).where(LINEA.c.item_crudo_id == item_id).values(estado_resolucion=estado)
        )
        if not resuelto:
            await _vaciar_producto_de_item(conexion, item_id)
    return {"item_id": str(item_id), "estado": estado, "sku": sku_usado}


async def _vaciar_producto_de_item(conexion: Any, item_id: uuid.UUID) -> None:
    """Deja las LINEA del item como un hueco del optimizador: sin producto ni precio.

    "Sin coincidencia" es decir "no lo tenemos". Si la linea conservara el
    producto que el optimizador eligio, `ordenar` la cobraria (cobra toda linea
    con sku y precio) mientras el acudiente la ve como hueco. Las alternativas
    se conservan: el revisor puede fijar una despues con `fijar_producto_en_linea`.
    """
    kits = [
        fila.kit_id
        for fila in await conexion.execute(
            select(LINEA.c.kit_id).where(LINEA.c.item_crudo_id == item_id).distinct()
        )
    ]
    await conexion.execute(
        update(LINEA)
        .where(LINEA.c.item_crudo_id == item_id)
        .values(
            producto_canonico_id=None,
            sku=None,
            nombre_producto=None,
            marca=None,
            nivel=None,
            personaje=None,
            imagen_url=None,
            confianza=None,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            precio_unitario_cop=None,
            subtotal_cop=None,
        )
    )
    for kit_id in kits:
        await _recalcular_total_kit(conexion, kit_id)


async def fijar_producto_en_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    sku: str,
    *,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """Fija un producto en UNA linea (un kit + un item) con su precio recalculado.

    La decision de producto es por-nivel (tres LINEA por item, una por kit),
    no por-item: `decidir_linea` escribe RESOLUCION y solo copia su estado a la
    LINEA —nunca cambia su producto—, asi que el kit publicado seguia mostrando
    el producto del optimizador. Esta es la
    ruta de escritura que faltaba. El producto se pide al catalogo (no al
    CANDIDATO) porque un personaje puede no ser candidato del item y aun asi ser
    una eleccion valida del revisor.

    `subtotal = precio * techo(cantidad_pedida / unidades_por_empaque)`, la misma
    aritmetica del armado (optimizador._construir_linea). Recalcula KIT.total_cop.
    """
    # Se niega antes de ir al catalogo: no tiene caso pagar la llamada HTTP.
    # Se vuelve a mirar dentro de la transaccion que escribe.
    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
    producto = await catalogo.producto(sku)
    precio = producto.get("precio_desde")
    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
        fila = (
            await conexion.execute(
                select(
                    LINEA.c.id,
                    LINEA.c.kit_id,
                    LINEA.c.cantidad_pedida,
                    LINEA.c.informativa,
                    LINEA.c.sku,
                    LINEA.c.nombre_producto,
                    LINEA.c.nivel,
                    LINEA.c.precio_unitario_cop,
                    LINEA.c.imagen_url,
                    LINEA.c.alternativas,
                )
                .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
                .where(
                    KIT.c.trabajo_id == trabajo_id,
                    KIT.c.perfil == perfil,
                    LINEA.c.item_crudo_id == item_id,
                )
            )
        ).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")

        # El producto que sale pasa a ser alternativa y el que entra deja de
        # serlo: sin esto la consola lo mostraba dos veces y el anterior ya no
        # se podia volver a elegir. Mismo tope de dos que pone el armado.
        alternativas = [a for a in (fila.alternativas or []) if a.get("sku") not in {sku, fila.sku}]
        if fila.sku and fila.sku != sku:
            anterior = {
                "sku": fila.sku,
                "nombre": fila.nombre_producto,
                "nivel": fila.nivel,
                "precio_cop": fila.precio_unitario_cop,
                "imagen_url": fila.imagen_url,
            }
            alternativas = [anterior, *alternativas]
        alternativas = alternativas[:2]

        # Una linea informativa no lleva precio (CHECK del modelo): fijarle un
        # producto no puede introducir un subtotal por la puerta de atras.
        empaque = int(producto.get("unidades_por_empaque") or 1)
        unidades = unidades_a_comprar(int(fila.cantidad_pedida or 0), empaque)
        subtotal = None if (fila.informativa or precio is None) else precio * unidades
        await conexion.execute(
            update(LINEA)
            .where(LINEA.c.id == fila.id)
            .values(
                sku=sku,
                nombre_producto=producto.get("nombre"),
                marca=producto.get("marca"),
                nivel=producto.get("nivel"),
                personaje=producto.get("personaje"),
                imagen_url=producto.get("imagen_url"),
                unidad_base=producto.get("unidad_base"),
                unidades_por_empaque=empaque,
                unidades_a_comprar=unidades,
                precio_unitario_cop=None if fila.informativa else precio,
                subtotal_cop=subtotal,
                alternativas=alternativas,
            )
        )
        await _recalcular_total_kit(conexion, fila.kit_id)
    return {"trabajo_id": str(trabajo_id), "perfil": perfil, "item_id": str(item_id), "sku": sku}


async def _proteger_kits_publicados(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Niega editar las lineas de unos kits canonicos ya publicados.

    Canonico es lo que no tiene acudiente (preview fijado, `canonico_lista`) o
    lo que la cache de su grado apunta hoy (datos de antes, cuando aprobar el
    trabajo de un acudiente tambien la fijaba). El trabajo publicado de un
    acudiente que no es la cache sigue el flujo de siempre.
    """
    fila = (
        await conexion.execute(select(TRABAJO.c.estado, TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id))
    ).one_or_none()
    if fila is None or fila.estado != EstadoTrabajo.PUBLICADO.value:
        return
    apuntado = await conexion.scalar(
        select(KIT_CANONICO.c.id).where(KIT_CANONICO.c.trabajo_id == trabajo_id).limit(1)
    )
    if fila.origen in ORIGENES_SIN_ACUDIENTE or apuntado is not None:
        raise KitsPublicadosNoEditables()


async def _recalcular_total_kit(conexion: Any, kit_id: uuid.UUID) -> None:
    await RepoTrabajos(conexion).recalcular_total_kit(kit_id)


async def revisar(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    decision: str,
    nota: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """AD-06: aprobar publica al acudiente, devolver reabre sin avisar."""
    # Devolver reencola: el trabajador durable (ADR 0024) lo retoma, no una tarea
    # en proceso. Antes iba a PROCESANDO y el API arrancaba la corrutina; ahora
    # queda ENCOLADO y el worker lo drena con SKIP LOCKED.
    nuevo = EstadoTrabajo.PUBLICADO.value if decision == "aprobar" else EstadoTrabajo.ENCOLADO.value
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if not puede_pasar(actual, nuevo):
            raise TransicionIlegal(actual, nuevo)
        # Un preview de onboarding no tiene acudiente (`usuario_id` NULL): no es
        # el trabajo del padre, es la vista de los kits que saldrian de la lista.
        # Publicarlo no avisa a nadie (el `kits_publicados` que emite se queda
        # sin destinatario y el repartidor lo reintenta sin fin) y no crea el
        # colegio (eso lo hace aprobar la LISTA en Catalogo). Lo que se hace con
        # un preview es fijarlo como canonico (`fijar_como_canonico`).
        if decision == "aprobar":
            origen = await conexion.scalar(select(TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id))
            if origen in ORIGENES_SIN_ACUDIENTE:
                raise PreviewNoPublicable()
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=nuevo,
                revisado_por=actor,
                revisado_en=ahora(),
                nota_revision=nota,
                terminado_en=ahora() if decision == "aprobar" else None,
            )
        )
        if decision == "aprobar":
            # No se publica un kit del que nadie puede comprar nada: si NINGUNA
            # linea de NINGUN perfil tiene producto+precio, el acudiente solo
            # veria el 409 "sin lineas comprables" en el checkout. Se niega la
            # aprobacion con un motivo claro (falta fijar producto/precio en las
            # lineas). Misma definicion de "comprable" que `ordenar`: no
            # informativa, con sku y precio.
            if not await _tiene_lineas_comprables(conexion, trabajo_id):
                raise CheckoutRechazado(
                    409,
                    {
                        "error": "kit_sin_lineas",
                        "mensaje": (
                            "Este trabajo no tiene ninguna linea con producto y precio "
                            "que Tukit pueda vender. Fija el producto en las lineas antes "
                            "de aprobarlo."
                        ),
                    },
                )
            await _publicar_evento(conexion, trabajo_id)
            # Aprobar el trabajo de un acudiente NO lo vuelve el canonico de su
            # grado: lleva sus preferencias (presupuesto, prioridad, personaje) y
            # es solo suyo. El canonico sale de la LISTA aprobada
            # (`canonico_lista`) o de un preview fijado (`fijar_como_canonico`).

    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}


async def _tiene_lineas_comprables(conexion: Any, trabajo_id: uuid.UUID) -> bool:
    """True si algun kit del trabajo tiene una linea que Tukit pueda cobrar.

    Comprable = no informativa, con `sku` y `precio_unitario_cop`. Es la misma
    condicion que filtra `ordenar` al armar la orden; se comparte aqui para que
    aprobar y comprar no discrepen sobre que es un kit vendible.
    """
    existe = await conexion.scalar(
        select(LINEA.c.id)
        .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
        .where(
            KIT.c.trabajo_id == trabajo_id,
            LINEA.c.informativa.is_(False),
            LINEA.c.sku.is_not(None),
            LINEA.c.precio_unitario_cop.is_not(None),
        )
        .limit(1)
    )
    return existe is not None


async def _fijar_canonico(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Al publicar, apunta la cache canonica de (colegio, grado, anio) a este trabajo."""
    await RepoTrabajos(conexion).fijar_canonico(trabajo_id)


def _identidad_de_grado(hijos: Any) -> tuple[str, str, int, str | None] | None:
    """(colegio, grado, anio, version_id) de un trabajo de UN solo hijo, o None."""
    lista = list(hijos or ())
    if len(lista) != 1:
        return None
    hijo = lista[0]
    colegio_id = str(hijo.get("colegio_id") or "")
    grado = str(hijo.get("grado") or "")
    if not (colegio_id and grado):
        return None
    anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
    version = hijo.get("version_id")
    return colegio_id, grado, anio, str(version) if version else None


async def version_canonica(conexion: Any, colegio_id: str, grado: str, anio: int) -> str | None:
    """La version de lista con que se armo el canonico vigente del grado.

    Sale del hijo del trabajo al que apunta la cache. None si no hay canonico o
    si el trabajo es anterior a que los hijos cargaran su `version_id`.
    """
    fila = (
        await conexion.execute(
            select(TRABAJO.c.hijos)
            .select_from(KIT_CANONICO.join(TRABAJO, TRABAJO.c.id == KIT_CANONICO.c.trabajo_id))
            .where(
                KIT_CANONICO.c.colegio_id == colegio_id,
                KIT_CANONICO.c.grado == grado,
                KIT_CANONICO.c.anio_lectivo == anio,
            )
        )
    ).one_or_none()
    if fila is None:
        return None
    identidad = _identidad_de_grado(fila.hijos)
    return identidad[3] if identidad else None


async def _cerrar_canonico_de_lista(conexion: Any, trabajo_id: uuid.UUID) -> str:
    """El cierre de un `canonico_lista`: publica sin avisar y fija la cache.

    No hay acudiente, asi que no se emite `kits_publicados` y no pasa por la
    cola de revision: la persona ya reviso la LISTA, que es lo que la aprobacion
    certifica, igual que en el kit del padre que esperaba (`lista_verificada`).

    Si mientras el optimizador corria alguien fijo a mano un canonico de ESTA
    misma version —aprobar desde el preview, con sus ajustes— ese gana: este
    trabajo sobra y se borra en vez de pisarle el puntero.
    """
    fila = (await conexion.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))).one_or_none()
    identidad = _identidad_de_grado(fila.hijos if fila else None)
    # `regenera` lo pone solo `poller.regenerar_canonicos`, que ya salto los
    # canonicos aprobados o corregidos a mano: ahi la version repetida es
    # justamente lo que se pidio rearmar.
    regenera = bool(next(iter(fila.hijos or ()), {}).get("regenera")) if fila else False
    if identidad and identidad[3] and not regenera:
        colegio_id, grado, anio, version = identidad
        if await version_canonica(conexion, colegio_id, grado, anio) == version:
            await conexion.execute(delete(TRABAJO).where(TRABAJO.c.id == trabajo_id))
            return "descartado"
    await _pasar_a(conexion, trabajo_id, EstadoTrabajo.PUBLICADO.value, terminado_en=ahora())
    await _fijar_canonico(conexion, trabajo_id)
    return EstadoTrabajo.PUBLICADO.value


async def fijar_como_canonico(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    nota: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Publica un trabajo SIN acudiente y lo deja como kit canonico de su grado.

    Es lo que hace "Aprobar la lista y guardar estos kits" desde un preview: el
    admin ya miro (y quiza ajusto) los tres kits, asi que esos —y no un calculo
    nuevo— son los que la ruta rapida le sirve al proximo acudiente. No emite
    `kits_publicados`: no hay a quien avisar.
    """
    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id)
            )
        ).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(str(trabajo_id))
        if fila.origen not in ORIGENES_SIN_ACUDIENTE:
            raise NoCanonizable()
        nuevo = EstadoTrabajo.PUBLICADO.value
        if not puede_pasar(fila.estado, nuevo):
            raise TransicionIlegal(fila.estado, nuevo)
        # Un borrador de edicion solo reemplaza al canonico del que salio: si
        # mientras tanto la lista se reaprobo, ese ya no es el vigente.
        basado_en = await _basado_en(conexion, trabajo_id)
        if basado_en and await _canonico_vigente_de(conexion, trabajo_id) != basado_en:
            raise BorradorDesactualizado()
        # La disponibilidad ("91% con precio confirmado") es la del armado; si
        # el admin fijo o vacio productos, se recalcula sobre lo que se publica.
        await _recalcular_objetivos(conexion, trabajo_id)
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=nuevo,
                revisado_por=actor,
                revisado_en=ahora(),
                nota_revision=nota,
                terminado_en=ahora(),
            )
        )
        await _fijar_canonico(conexion, trabajo_id)
    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}


# ---------------------------------------------------------------------------
# Versiones de los kits canonicos: editar es copiar y volver a publicar
# ---------------------------------------------------------------------------


async def _basado_en(conexion: Any, trabajo_id: uuid.UUID) -> uuid.UUID | None:
    """El canonico del que se copio este borrador, o None si no es un borrador."""
    hijos = await conexion.scalar(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    origen = next(iter(hijos or ()), {}).get("basado_en")
    return uuid.UUID(str(origen)) if origen else None


async def _canonico_vigente_de(conexion: Any, trabajo_id: uuid.UUID) -> uuid.UUID | None:
    """El trabajo al que apunta hoy la cache del (colegio, grado, anio) de este."""
    hijos = await conexion.scalar(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    identidad = _identidad_de_grado(hijos)
    if identidad is None:
        return None
    colegio_id, grado, anio, _ = identidad
    return await conexion.scalar(
        select(KIT_CANONICO.c.trabajo_id).where(
            KIT_CANONICO.c.colegio_id == colegio_id,
            KIT_CANONICO.c.grado == grado,
            KIT_CANONICO.c.anio_lectivo == anio,
        )
    )


async def _borrador_abierto(conexion: Any, canonico_id: uuid.UUID) -> uuid.UUID | None:
    """El borrador sin publicar que ya salio de este canonico, si hay uno.

    `basado_en` vive en el JSON `hijos`, no en una columna: se filtra en memoria
    sobre los pocos `canonico_lista` en revision (los del poller se publican
    solos y nunca quedan aqui).
    """
    filas = await conexion.execute(
        select(TRABAJO.c.id, TRABAJO.c.hijos)
        .where(
            TRABAJO.c.origen == ORIGEN_CANONICO,
            TRABAJO.c.estado == EstadoTrabajo.ESPERA_REVISION.value,
        )
        .order_by(TRABAJO.c.creado_en)
    )
    for fila in filas:
        if str(next(iter(fila.hijos or ()), {}).get("basado_en")) == str(canonico_id):
            return fila.id
    return None


async def _copiar_filas(
    conexion: Any, tabla: Any, filas: list[Any], **remapeos: dict[Any, Any]
) -> dict[Any, Any]:
    """Inserta copias de `filas` con id nuevo; `remapeos` traduce sus FKs.

    Devuelve {id viejo: id nuevo} para que la tabla hija remapee las suyas.
    """
    nuevos: dict[Any, Any] = {}
    for fila in filas:
        valores = dict(fila._mapping)
        nuevos[valores["id"]] = valores["id"] = uuid.uuid4()
        for columna, mapa in remapeos.items():
            if valores.get(columna) is not None:
                valores[columna] = mapa[valores[columna]]
        await conexion.execute(insert(tabla).values(**valores))
    return nuevos


async def abrir_borrador(motor: Any, canonico_id: uuid.UUID) -> dict[str, Any]:
    """Una copia editable de los kits canonicos vigentes de un grado.

    Los kits publicados no se editan en sitio: el acudiente que ya empezo
    apunta a ese trabajo (`hijos[0].canonico_trabajo_id`) y debe seguir viendo
    lo que pago. Se copia el trabajo entero —items, candidatos, resoluciones,
    kits y lineas, con ids nuevos— a un `canonico_lista` en `espera_revision`
    que la consola de siempre corrige, y `fijar_como_canonico` lo publica como
    la version nueva. El historial de transiciones no se copia: es del original.

    Idempotente: si el canonico ya tiene un borrador abierto, devuelve ese.
    """
    async with motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == canonico_id))).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(str(canonico_id))
        # Cualquier canonico vigente, aunque haya salido del trabajo aprobado de
        # un acudiente: la copia no lleva su usuario ni sus preferencias.
        if await _canonico_vigente_de(conexion, canonico_id) != canonico_id:
            raise BorradorDesactualizado()
        abierto = await _borrador_abierto(conexion, canonico_id)
        if abierto is not None:
            return {"trabajo_id": str(abierto), "basado_en": str(canonico_id), "nuevo": False}

        borrador_id = uuid.uuid4()
        hijos = [dict(h) for h in fila.hijos or ()]
        hijos[0]["basado_en"] = str(canonico_id)
        await conexion.execute(
            insert(TRABAJO).values(
                id=borrador_id,
                usuario_id=None,
                estado=EstadoTrabajo.ESPERA_REVISION.value,
                origen=ORIGEN_CANONICO,
                hijos=hijos,
                estimado_segundos=fila.estimado_segundos,
                degradaciones=list(fila.degradaciones or ()),
            )
        )
        etapas = list(await conexion.execute(select(ETAPA).where(ETAPA.c.trabajo_id == canonico_id)))
        await _copiar_filas(conexion, ETAPA, etapas, trabajo_id={canonico_id: borrador_id})
        items = list(await conexion.execute(select(ITEM).where(ITEM.c.trabajo_id == canonico_id)))
        mapa_items = await _copiar_filas(conexion, ITEM, items, trabajo_id={canonico_id: borrador_id})
        de_items = list(mapa_items)
        candidatos = list(
            await conexion.execute(select(CANDIDATO).where(CANDIDATO.c.item_crudo_id.in_(de_items)))
        )
        mapa_candidatos = await _copiar_filas(conexion, CANDIDATO, candidatos, item_crudo_id=mapa_items)
        resoluciones = list(
            await conexion.execute(select(RESOLUCION).where(RESOLUCION.c.item_crudo_id.in_(de_items)))
        )
        await _copiar_filas(
            conexion,
            RESOLUCION,
            resoluciones,
            item_crudo_id=mapa_items,
            candidato_item_id=mapa_candidatos,
        )
        kits = list(await conexion.execute(select(KIT).where(KIT.c.trabajo_id == canonico_id)))
        mapa_kits = await _copiar_filas(conexion, KIT, kits, trabajo_id={canonico_id: borrador_id})
        lineas = list(await conexion.execute(select(LINEA).where(LINEA.c.kit_id.in_(list(mapa_kits)))))
        await _copiar_filas(conexion, LINEA, lineas, kit_id=mapa_kits, item_crudo_id=mapa_items)
    return {"trabajo_id": str(borrador_id), "basado_en": str(canonico_id), "nuevo": True}


async def _recalcular_objetivos(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Pone al dia costo, fidelidad y disponibilidad de cada kit del trabajo.

    Misma regla que el kit aplicado de la ruta rapida (`_objetivos_de_lineas`);
    las demas llaves del armado (p. ej. `resolucion_auto`) se conservan.
    """
    for kit in list(await conexion.execute(select(KIT).where(KIT.c.trabajo_id == trabajo_id))):
        lineas = [
            _linea_publica(f) for f in await conexion.execute(select(LINEA).where(LINEA.c.kit_id == kit.id))
        ]
        total = sum(int(linea["subtotal_linea"] or 0) for linea in lineas)
        objetivos = {**(kit.objetivos or {}), **_objetivos_de_lineas(lineas, total)}
        await conexion.execute(
            update(KIT).where(KIT.c.id == kit.id).values(objetivos=objetivos, total_cop=total)
        )


async def grados_canonicos(motor: Any, *, colegio_id: str | None = None) -> list[dict[str, Any]]:
    """Los (colegio, grado, anio) que ya tienen cache bendita, para el selector.

    Es lo que `/empezar` lista en vez de pedir un PDF: un grado que aparece aqui
    se puede aplicar al vuelo (ruta rapida); uno que no, entra al pipeline.
    """
    consulta = (
        select(
            KIT_CANONICO.c.colegio_id,
            KIT_CANONICO.c.grado,
            KIT_CANONICO.c.anio_lectivo,
            KIT_CANONICO.c.trabajo_id,
            TRABAJO.c.terminado_en,
        )
        .select_from(KIT_CANONICO.join(TRABAJO, TRABAJO.c.id == KIT_CANONICO.c.trabajo_id))
        .order_by(KIT_CANONICO.c.colegio_id, KIT_CANONICO.c.grado)
    )
    if colegio_id:
        consulta = consulta.where(KIT_CANONICO.c.colegio_id == colegio_id)
    async with motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))
        # Solo el admin de un colegio pregunta por su borrador; el selector de
        # /empezar (sin colegio) no paga esa consulta.
        borradores = (
            {f.trabajo_id: await _borrador_abierto(conexion, f.trabajo_id) for f in filas}
            if colegio_id
            else {}
        )
    return [
        {
            "colegio_id": f.colegio_id,
            "grado": f.grado,
            "anio_lectivo": int(f.anio_lectivo),
            "trabajo_id": str(f.trabajo_id),
            "publicado_en": f.terminado_en.isoformat() if f.terminado_en else None,
            "borrador_trabajo_id": (str(borradores[f.trabajo_id]) if borradores.get(f.trabajo_id) else None),
        }
        for f in filas
    ]


async def acudientes_de_colegio(motor: Any, *, colegio_id: str) -> list[dict[str, Any]]:
    """Los acudientes de un colegio con el estado de su trabajo más reciente.

    Agrupa por `usuario_id` (el identificador del acudiente, jamás su correo ni
    el nombre de un menor) y se queda con el trabajo VIVO: el más nuevo de cada
    acudiente. El colegio no es columna del trabajo —vive en el JSON `hijos`—,
    así que el filtro es por ese campo. Los trabajos anónimos (sin `usuario_id`)
    no se agrupan: no hay a quién listar.

    Devuelve además los `grados` que ese acudiente pidió EN ESTE colegio (de los
    hijos que le corresponden) y las `preferencias` del hogar descifradas —pesos,
    presupuesto, personaje—: dato de negocio, no PII (no lleva correo ni el
    nombre del menor), y es lo que el panel necesita para atenderlo sin abrir el
    trabajo.
    """
    cifrador = cifrador_desde_entorno()
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.usuario_id,
            TRABAJO.c.estado,
            TRABAJO.c.actualizado_en,
            TRABAJO.c.hijos,
            TRABAJO.c.preferencias_cifradas,
        )
        .where(TRABAJO.c.usuario_id.is_not(None))
        .order_by(TRABAJO.c.usuario_id, TRABAJO.c.actualizado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = (await conexion.execute(consulta)).all()

    # ponytail: filtro por colegio en Python sobre los trabajos recientes — un
    # colegio tiene decenas de acudientes, no hace falta índice sobre el JSON.
    # Subir a JSON containment (`hijos @> …`) si un colegio pasa de miles.
    ultimos: dict[str, Any] = {}
    for f in filas:  # ya vienen por usuario, más reciente primero
        if any(h.get("colegio_id") == colegio_id for h in (f.hijos or ())):
            ultimos.setdefault(str(f.usuario_id), f)

    def _grados_en_colegio(f: Any) -> list[str]:
        # Solo los grados de los hijos de ESTE colegio, sin repetir. Un hogar
        # tiene uno o dos: orden alfabético basta, no vale un índice canónico.
        grados = {h["grado"] for h in (f.hijos or ()) if h.get("colegio_id") == colegio_id and h.get("grado")}
        return sorted(grados)

    return [
        {
            "usuario_id": uid,
            "estado": f.estado,
            "actualizado_en": f.actualizado_en.isoformat() if f.actualizado_en else None,
            "trabajo_id": str(f.id),
            "grados": _grados_en_colegio(f),
            "preferencias": cifrador.descifrar_json(f.preferencias_cifradas) or {}
            if f.preferencias_cifradas
            else {},
        }
        for uid, f in ultimos.items()
    ]


async def mis_trabajos(motor: Any, *, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    """Los trabajos (solicitudes de kit) de UN acudiente, del mas nuevo al mas viejo.

    Es la lectura del panel del acudiente: sus solicitudes de kit —lo que
    `/empezar` crea—, que no son pedidos pagados (esos los sirve comercio) sino
    trabajos del pipeline. Devuelve por cada uno el estado, los hijos (por
    `referencia`/`colegio_id`/`grado`, jamas un nombre de menor) y las
    preferencias del hogar descifradas, que son del titular y las pidio el.
    """
    cifrador = cifrador_desde_entorno()
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.hijos,
            TRABAJO.c.preferencias_cifradas,
            TRABAJO.c.creado_en,
        )
        .where(TRABAJO.c.usuario_id == usuario_id)
        .order_by(TRABAJO.c.creado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = (await conexion.execute(consulta)).all()

    return [
        {
            "trabajo_id": str(f.id),
            "estado": f.estado,
            "creado_en": f.creado_en.isoformat() if f.creado_en else None,
            "hijos": list(f.hijos or ()),
            "preferencias": cifrador.descifrar_json(f.preferencias_cifradas) or {}
            if f.preferencias_cifradas
            else {},
        }
        for f in filas
    ]


async def _anclas_de_personaje(catalogo: ClienteCatalogo, personaje: str | None) -> dict[str, dict[str, Any]]:
    """Los productos de las cuatro anclas para un personaje, indexados por concepto.

    Vacio si no hay personaje. Es I/O de red: se resuelve FUERA de cualquier
    transaccion abierta. Un ancla que el catalogo no surte simplemente no entra
    (el kit queda con su producto neutral en ese concepto).
    """
    swaps: dict[str, dict[str, Any]] = {}
    if personaje:
        for concepto in CONCEPTOS_ANCLA:
            producto = await catalogo.producto_de_personaje(concepto, personaje)
            if producto:
                swaps[concepto] = producto
    return swaps


def _objetivos_de_lineas(lineas: list[dict[str, Any]], total: int) -> dict[str, float | int]:
    """Los objetivos de display de un kit aplicado, desde sus lineas publicas.

    El kit de la ruta rapida no tiene fila propia en `kit` (es un puntero al
    canonico, con el personaje aplicado), asi que sus objetivos se recalculan
    con la misma regla que `optimizador._objetivos`: solo lo comprable, la
    fidelidad como nivel de marca promedio en [0, 1] y la disponibilidad como
    fraccion de lineas con precio. Sin esto iban vacios y la web pintaba
    "NaN% con precio confirmado".
    """
    comprables = [linea for linea in lineas if not linea["informativa"] and not linea.get("descartado")]
    if not comprables:
        return {"costo": total, "fidelidad": 0.0, "disponibilidad": 0.0}
    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    suma_fidelidad = 0.0
    con_precio = 0
    for linea in comprables:
        producto = linea.get("producto_elegido") or {}
        nivel = producto.get("nivel")
        if nivel is not None:
            rango = ORDEN_NIVEL.index(nivel) if nivel in ORDEN_NIVEL else len(ORDEN_NIVEL)
            suma_fidelidad += rango / tope_nivel
        if producto.get("precio") is not None:
            con_precio += 1
    return {
        "costo": total,
        "fidelidad": round(suma_fidelidad / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
    }


def _alternativa_de(producto: dict[str, Any]) -> dict[str, Any]:
    """Un producto elegido, con la forma de una alternativa guardada en la linea."""
    return {
        "sku": producto.get("sku"),
        "nombre": producto.get("nombre"),
        "nivel": producto.get("nivel"),
        "precio_cop": producto.get("precio"),
        "imagen_url": producto.get("imagen_url"),
    }


def _aplicar_cambios(
    lineas: list[dict[str, Any]], cambios_del_kit: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Las lineas de un kit con lo que el acudiente cambio, y su total.

    Un cambio puede traer un producto elegido (`sku`) y/o la marca `descartado`.
    El producto elegido reemplaza al de su linea con la misma aritmetica del
    armado (techo(pedida/empaque)) y deja el sugerido como una alternativa mas,
    para que siempre se pueda volver a el; la linea queda marcada
    (`cambiado_por_acudiente`, `sku_sugerido`) para que la pantalla lo diga.
    Una linea descartada ("ya lo tengo") se queda en el kit, marcada
    `descartado`, pero sin subtotal: no suma al total y no entra a la orden. Su
    subtotal anterior viaja en `subtotal_descartado` para poder mostrar cuanto
    se ahorra y deshacerlo. El total se vuelve a sumar desde las lineas, que es
    como lo suma el armado (`_recalcular_total_kit`).
    """
    salida: list[dict[str, Any]] = []
    for linea in lineas:
        cambio = cambios_del_kit.get(str(linea.get("item_id")))
        sugerido = linea.get("producto_elegido")
        if cambio and sugerido and not linea["informativa"]:
            linea = dict(linea)
            if cambio.get("sku"):
                empaque = int(cambio.get("unidades_por_empaque") or 1)
                precio = cambio.get("precio")
                unidades = unidades_a_comprar(int(linea.get("cantidad_pedida") or 0), empaque)
                linea["producto_elegido"] = {
                    "sku": cambio.get("sku"),
                    "nombre": cambio.get("nombre"),
                    "marca": cambio.get("marca"),
                    "nivel": cambio.get("nivel"),
                    "personaje": cambio.get("personaje"),
                    "imagen_url": cambio.get("imagen_url"),
                    "precio": precio,
                }
                linea["unidades_por_empaque"] = empaque
                linea["unidades_a_comprar"] = unidades
                linea["subtotal_linea"] = None if precio is None else precio * unidades
                linea["alternativas"] = [_alternativa_de(sugerido)] + [
                    a for a in (linea.get("alternativas") or []) if a.get("sku") != cambio.get("sku")
                ]
                linea["cambiado_por_acudiente"] = True
                linea["sku_sugerido"] = sugerido.get("sku")
            if cambio.get("descartado"):
                linea["descartado"] = True
                linea["subtotal_descartado"] = linea.get("subtotal_linea")
                linea["subtotal_linea"] = None
        salida.append(linea)
    total = sum(
        int(linea.get("subtotal_linea") or 0)
        for linea in salida
        if not linea["informativa"] and not linea.get("descartado")
    )
    return salida, total


async def _linea_para_cambiar(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """La cabeza del trabajo, su kit y la linea que el acudiente quiere tocar.

    Las reglas de quien puede cambiar y que se puede cambiar viven aqui, en un
    solo sitio, porque las comparten cambiar el producto y descartarlo: el
    trabajo con dueno solo lo toca el dueno, el kit tiene que estar publicado, y
    una linea sin producto o consolidada con la de un hermano no se toca por
    separado.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.usuario_id, TRABAJO.c.cambios).where(
                    TRABAJO.c.id == trabajo_id
                )
            )
        ).one_or_none()
    if cabeza is None:
        raise TrabajoNoExiste(str(trabajo_id))
    if cabeza.usuario_id is not None and cabeza.usuario_id != usuario_id:
        raise CambioNoPermitido(
            "solicitud_ajena", "Inicia sesión con la cuenta que hizo esta solicitud para cambiarla.", 403
        )
    if cabeza.estado != EstadoTrabajo.PUBLICADO.value:
        raise CambioNoPermitido("kit_no_publicado", "Tu kit todavía no está listo para cambios.")

    vista = await ver(motor, trabajo_id, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    linea = next((ln for ln in (kit or {}).get("lineas", []) if ln["item_id"] == str(item_id)), None)
    if kit is None or linea is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")
    actual = linea.get("producto_elegido")
    if linea["informativa"] or not actual:
        raise CambioNoPermitido("linea_sin_producto", "Este renglón no tiene un producto para cambiar.")
    # Un producto que se compra junto con el de un hermano no se cambia por
    # separado: la consolidacion lo comparte entre los dos.
    if any(c.get("sku") == actual.get("sku") for c in kit.get("consolidaciones") or []):
        raise CambioNoPermitido(
            "linea_consolidada",
            "Este producto se compra junto con el de tu otro hijo y no se cambia por separado.",
        )
    return cabeza, kit, linea


async def _guardar_cambios(motor: Any, trabajo_id: uuid.UUID, cambios: dict[str, Any]) -> None:
    cambios = {p: {i: c for i, c in kit.items() if c} for p, kit in cambios.items()}
    cambios = {p: c for p, c in cambios.items() if c}
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(cambios=cambios, actualizado_en=ahora())
        )


async def cambiar_producto_del_acudiente(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    sku: str,
    *,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """El acudiente cambia el producto de una linea por una de sus alternativas.

    Solo se acepta un producto que ya estaba en la linea (el sugerido o una de
    sus alternativas): el papa elige entre lo que una persona reviso, no
    cualquier sku. El cambio se guarda en `cambios` de SU trabajo y `ver` lo
    aplica al leer; volver al sugerido borra el cambio. Si el trabajo tiene
    dueno, solo el puede cambiarlo.
    """
    cabeza, _kit, linea = await _linea_para_cambiar(
        motor, trabajo_id, perfil, item_id, usuario_id=usuario_id, catalogo=catalogo
    )
    actual = linea["producto_elegido"]
    permitidos = {actual.get("sku")} | {a.get("sku") for a in linea.get("alternativas") or []}
    producto: dict[str, Any] | None = None
    if sku not in permitidos:
        # Fuera de las alternativas revisadas, se acepta cualquier producto del
        # MISMO concepto: es el mismo tipo de util, solo cambia marca o empaque.
        producto = await _producto_del_mismo_concepto(catalogo, sku, linea.get("concepto"))
        if producto is None:
            raise CambioNoPermitido(
                "producto_no_permitido", "Ese producto no es una opción para este renglón.", 422
            )
    respuesta = {"trabajo_id": str(trabajo_id), "perfil": perfil, "item_id": str(item_id), "sku": sku}
    if sku == actual.get("sku"):
        return respuesta

    cambios = {p: {i: dict(c) for i, c in kit.items()} for p, kit in dict(cabeza.cambios or {}).items()}
    del_item = cambios.setdefault(perfil, {}).setdefault(str(item_id), {})
    sugerido = linea.get("sku_sugerido") or actual.get("sku")
    if sku == sugerido:
        # Volver al sugerido borra el producto pero respeta un descarte vigente.
        descartado = del_item.get("descartado")
        del_item.clear()
        if descartado:
            del_item["descartado"] = True
    else:
        producto = producto or await catalogo.producto(sku)
        precio = producto.get("precio_desde")
        if precio is None:
            raise CambioNoPermitido("producto_sin_precio", "Ese producto no tiene precio hoy; elige otro.")
        del_item.update(
            {
                "sku": sku,
                "nombre": producto.get("nombre"),
                "marca": producto.get("marca"),
                "nivel": producto.get("nivel"),
                "personaje": producto.get("personaje"),
                "imagen_url": producto.get("imagen_url"),
                "unidades_por_empaque": int(producto.get("unidades_por_empaque") or 1),
                "precio": int(precio),
            }
        )
    await _guardar_cambios(motor, trabajo_id, cambios)
    return respuesta


async def _producto_del_mismo_concepto(
    catalogo: ClienteCatalogo, sku: str, concepto: str | None
) -> dict[str, Any] | None:
    """El producto `sku` si pertenece al `concepto` de la linea; `None` si no."""
    if not concepto:
        return None
    try:
        producto = await catalogo.producto(sku)
    except (KeyError, RemotoCaido):
        return None
    if (producto.get("concepto") or {}).get("codigo") != concepto:
        return None
    return producto


async def opciones_de_la_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """Las opciones del mismo concepto para una linea, con lo que cambiaria el total.

    Es la lectura del carrusel de "cambiar por otra opcion": cada producto
    trae imagen, marca, nivel, precio del empaque, empaque y el subtotal que
    tendria la linea con el (misma aritmetica del armado). `diferencia` es contra
    lo que cuesta hoy la linea; `en_kit` marca el elegido y `sugerido` el que
    traia el kit antes de cualquier cambio.
    """
    vista = await ver(motor, trabajo_id, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    linea = next((ln for ln in (kit or {}).get("lineas", []) if ln["item_id"] == str(item_id)), None)
    if kit is None or linea is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")
    actual = linea.get("producto_elegido") or {}
    concepto = linea.get("concepto")
    if linea["informativa"] or not actual or not concepto:
        return {"item_id": str(item_id), "concepto": concepto, "opciones": []}
    # Si la linea esta descartada, el subtotal "de hoy" es el que tendria
    # reactivada: asi la diferencia no se compara contra cero.
    subtotal_hoy = linea.get("subtotal_descartado") if linea.get("descartado") else linea.get("subtotal_linea")
    sugerido = linea.get("sku_sugerido") or actual.get("sku")
    pedida = int(linea.get("cantidad_pedida") or 0)

    productos = await catalogo.productos_del_concepto(str(concepto))
    por_sku = {p["sku"]: p for p in productos}
    # El elegido y las alternativas revisadas siempre estan, aunque el catalogo
    # ya no los devuelva en la pagina.
    for conocido in [actual, *(linea.get("alternativas") or [])]:
        sku = conocido.get("sku")
        if sku and sku not in por_sku:
            precio = conocido.get("precio", conocido.get("precio_cop"))
            if precio is not None:
                por_sku[sku] = {**conocido, "precio_desde": precio, "unidades_por_empaque": 1}

    opciones = []
    for p in por_sku.values():
        precio = p.get("precio_desde")
        if precio is None:
            continue
        empaque = int(p.get("unidades_por_empaque") or 1)
        unidades = unidades_a_comprar(pedida, empaque)
        subtotal = int(precio) * unidades
        opciones.append(
            {
                "sku": p["sku"],
                "nombre": p.get("nombre"),
                "marca": p.get("marca"),
                "nivel": p.get("nivel"),
                "personaje": p.get("personaje"),
                "imagen_url": p.get("imagen_url"),
                "precio": int(precio),
                "unidades_por_empaque": empaque,
                "unidades_a_comprar": unidades,
                "subtotal": subtotal,
                "diferencia": None if subtotal_hoy is None else subtotal - int(subtotal_hoy),
                "en_kit": p["sku"] == actual.get("sku"),
                "sugerido": p["sku"] == sugerido,
            }
        )
    # El del kit primero, luego de menor a mayor precio de la linea.
    opciones.sort(key=lambda o: (not o["en_kit"], o["subtotal"]))
    return {"item_id": str(item_id), "concepto": concepto, "opciones": opciones}


async def descartar_linea_del_acudiente(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    descartar: bool,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """El acudiente quita una linea de su kit ("ya lo tengo") o la vuelve a poner.

    Se guarda como una marca en `cambios` de SU trabajo, igual que un cambio de
    producto: `ver` la aplica al leer (la linea no suma al total) y `ordenar`
    lee `ver`, asi que lo descartado tampoco se cobra. Es reversible y no toca
    las filas del kit, que pueden ser el canonico de otros acudientes.
    """
    cabeza, _kit, _linea = await _linea_para_cambiar(
        motor, trabajo_id, perfil, item_id, usuario_id=usuario_id, catalogo=catalogo
    )
    cambios = {p: {i: dict(c) for i, c in kit.items()} for p, kit in dict(cabeza.cambios or {}).items()}
    del_item = cambios.setdefault(perfil, {}).setdefault(str(item_id), {})
    if descartar:
        del_item["descartado"] = True
    else:
        del_item.pop("descartado", None)
    await _guardar_cambios(motor, trabajo_id, cambios)
    return {
        "trabajo_id": str(trabajo_id),
        "perfil": perfil,
        "item_id": str(item_id),
        "descartado": descartar,
    }


async def _lineas_aplicadas(
    conexion: Any, canonico_trabajo_id: uuid.UUID, perfil: str, swaps: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Las lineas del kit canonico de un perfil, con el personaje aplicado y el total.

    Es la fuente unica del kit aplicado: la usan tanto `aplicar_canonico` (para
    congelar el pedido) como `ver` (para pintarle al acudiente su kit sin copiar
    filas). Sobre un ancla con personaje elegido congela el producto del
    personaje en vez del neutral, con la misma aritmetica del armado
    (techo(pedida/empaque)); una linea informativa nunca lleva precio.
    """
    kit = (
        await conexion.execute(
            select(KIT.c.id, KIT.c.perfil).where(
                KIT.c.trabajo_id == canonico_trabajo_id, KIT.c.perfil == perfil
            )
        )
    ).one_or_none()
    if kit is None:
        raise TrabajoNoExiste(f"{canonico_trabajo_id}/{perfil}")

    lineas: list[dict[str, Any]] = []
    total = 0
    filas = await conexion.execute(
        select(LINEA, RESOLUCION.c.concepto_codigo)
        .select_from(
            LINEA.join(
                RESOLUCION,
                RESOLUCION.c.item_crudo_id == LINEA.c.item_crudo_id,
                isouter=True,
            )
        )
        .where(LINEA.c.kit_id == kit.id)
        .order_by(LINEA.c.hijo_referencia, LINEA.c.orden)
    )
    for fila in filas:
        linea = _linea_publica(fila)
        concepto = getattr(fila, "concepto_codigo", None)
        swap = swaps.get(concepto) if concepto else None
        if swap and not fila.informativa:
            empaque = int(swap.get("unidades_por_empaque") or 1)
            precio = swap.get("precio_desde")
            unidades = unidades_a_comprar(int(fila.cantidad_pedida or 0), empaque)
            linea["producto_elegido"] = {
                "sku": swap.get("sku"),
                "nombre": swap.get("nombre"),
                "marca": swap.get("marca"),
                "nivel": swap.get("nivel"),
                "personaje": swap.get("personaje"),
                "imagen_url": swap.get("imagen_url"),
                "precio": precio,
            }
            linea["unidades_por_empaque"] = empaque
            linea["unidades_a_comprar"] = unidades
            linea["subtotal_linea"] = None if precio is None else precio * unidades
        if not linea["informativa"] and linea.get("subtotal_linea"):
            total += int(linea["subtotal_linea"])
        lineas.append(linea)
    return lineas, total


async def aplicar_canonico(
    motor: Any,
    *,
    colegio_id: str,
    grado: str,
    anio_lectivo: int,
    perfil: str,
    personaje: str | None = None,
    usuario_id: uuid.UUID | None = None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    """La ruta rapida del acudiente: aplica su nivel + personaje a la cache bendita.

    NO re-optimiza (los tres kits ya los valido una persona; re-rankear
    arriesga sacar un producto no aprobado) y NO entra a la cola. Crea un
    trabajo `parent_apply` que es un puntero durable —no una copia de los kits—:
    referencia al trabajo canonico y guarda la seleccion (nivel + personaje).
    La UNICA copia que se congela es la del PEDIDO, porque es lo que se compra;
    ese snapshot viaja en el evento de la bandeja hacia Comercio (hoy sin
    repartidor: mismo patron de outbox sin consumidor que `kits_publicados`).

    El personaje se aplica al vuelo sobre las cuatro anclas (`CONCEPTOS_ANCLA`)
    con la misma consulta de catalogo que el interruptor del Fan; el resto del
    kit es neutral y no se toca. Devuelve el trabajo creado y el total congelado.
    """
    # Las anclas se resuelven contra el catalogo ANTES de abrir la transaccion:
    # es I/O de red y no debe tener una transaccion abierta esperandola.
    swaps = await _anclas_de_personaje(catalogo, personaje)

    parent_id = uuid.uuid4()
    async with motor.engine.begin() as conexion:
        canonico = (
            await conexion.execute(
                select(KIT_CANONICO.c.trabajo_id).where(
                    KIT_CANONICO.c.colegio_id == colegio_id,
                    KIT_CANONICO.c.grado == grado,
                    KIT_CANONICO.c.anio_lectivo == anio_lectivo,
                )
            )
        ).one_or_none()
        if canonico is None:
            raise TrabajoNoExiste(f"cache {colegio_id}/{grado}/{anio_lectivo}")

        # El Fan es el Ahorrador canonico con el personaje en las anclas: los
        # canonicos ya no traen Fan (ADR 0030). Los demas perfiles no llevan
        # personaje. `A tu Medida` no sale de la cache: depende de cada acudiente.
        if perfil == PerfilKit.FAN.value:
            base, swaps_kit = PerfilKit.AHORRADOR.value, swaps
        elif perfil in (PerfilKit.AHORRADOR.value, PerfilKit.PREMIUM.value):
            base, swaps_kit = perfil, {}
        else:
            raise TrabajoNoExiste(f"cache {colegio_id}/{grado}/{anio_lectivo}/{perfil}")
        lineas_frias, total = await _lineas_aplicadas(conexion, canonico.trabajo_id, base, swaps_kit)

        # El trabajo del acudiente: un registro durable, sin etapas de pipeline.
        # `hijos` lleva la seleccion entera porque es la ENTRADA de este trabajo
        # (se lee completa o no se lee), igual que en un trabajo de onboarding.
        await conexion.execute(
            insert(TRABAJO).values(
                id=parent_id,
                usuario_id=usuario_id,
                estado=EstadoTrabajo.PUBLICADO.value,
                origen="parent_apply",
                hijos=[
                    {
                        "colegio_id": colegio_id,
                        "grado": grado,
                        "anio_lectivo": anio_lectivo,
                        "canonico_trabajo_id": str(canonico.trabajo_id),
                        "perfil": perfil,
                        "personaje": personaje,
                    }
                ],
                terminado_en=ahora(),
            )
        )
        # El PEDIDO: el snapshot congelado de lo que se compra. Comercio (sin
        # portar) lo recogera de aqui; mientras, se escribe y nadie lo consume,
        # igual que `kits_publicados`.
        await conexion.execute(
            insert(BANDEJA).values(
                tipo="pedido_solicitado",
                agregado_tipo="trabajo_pipeline",
                agregado_id=parent_id,
                carga={
                    "trabajo_id": str(parent_id),
                    "canonico_trabajo_id": str(canonico.trabajo_id),
                    "usuario_id": str(usuario_id) if usuario_id else None,
                    "colegio_id": colegio_id,
                    "grado": grado,
                    "anio_lectivo": anio_lectivo,
                    "perfil": perfil,
                    "personaje": personaje,
                    "total_cop": total,
                    "lineas": lineas_frias,
                    "solicitado_en": ahora().isoformat(),
                },
            )
        )
    return {"trabajo_id": str(parent_id), "perfil": perfil, "personaje": personaje, "total": total}
