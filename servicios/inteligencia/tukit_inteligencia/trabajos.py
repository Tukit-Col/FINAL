"""El recurso `trabajo`: crear, procesar por etapas, consultar y revisar.

Aqui vive la maquina de estados que el contrato promete y la orquestacion de
las cuatro etapas. Lo que hay que entender de este modulo es que **el estado
no vive en el proceso**: cada transicion y cada etapa se escriben en la base
antes de seguir. La consecuencia practica es que reiniciar el servicio no
pierde los trabajos en vuelo, que `GET /v1/trabajos/{id}` puede responder
desde otro proceso, y que reanudar no vuelve a pagar la percepcion, que es la
etapa cara.

La ejecucion de fondo es una `asyncio.Task` del mismo proceso, y eso **si**
es una version simple a mejorar. Un trabajo que se este procesando cuando el
servicio se caiga se queda en `procesando` para siempre hasta que alguien lo
reencole; una cola de verdad (un trabajador aparte leyendo de la bandeja) lo
retomaria solo. Se deja asi a proposito para que el ciclo completo corra con
un comando, y se anota aqui para que no se confunda con lo definitivo.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, insert, select, update
from tukit_comun.cifrado import cifrador_desde_entorno

from .modelos import (
    PESOS_POR_OMISION,
    Base,
    EstadoEtapa,
    EstadoResolucion,
    EstadoTrabajo,
    puede_pasar,
)
from .modelos.trabajo import ETAPAS
from .optimizador import (
    CONCEPTOS_ANCLA,
    Candidato,
    Renglon,
    anclar_personaje,
    armar_los_tres,
    unidades_a_comprar,
)
from .parseo import BUSCA_EN_CATALOGO, Demanda, mensaje_para_papa, parsear_renglon
from .remoto import ClienteCatalogo, ClienteComercio, ClienteIdentidad, RemotoCaido

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


class TrabajoNoExiste(Exception):
    pass


class CheckoutRechazado(Exception):
    """Comercio rechazo la orden por una razon de negocio (p.ej. precio cambio).

    Lleva el estado HTTP y el cuerpo de Comercio para que el acudiente vea el
    motivo exacto (`precio_cambiado` y el nuevo precio), no un 500 generico.
    """

    def __init__(self, estado: int, cuerpo: dict[str, Any]) -> None:
        super().__init__(str(cuerpo.get("error") or estado))
        self.estado = estado
        self.cuerpo = cuerpo


class TransicionIlegal(Exception):
    def __init__(self, actual: str, pedida: str) -> None:
        super().__init__(f"no se puede pasar de {actual} a {pedida}")
        self.actual = actual
        self.pedida = pedida


class TrabajoProtegido(Exception):
    """Un trabajo `publicado` no se borra: es (o alimenta) el kit canonico."""

    def __init__(self, estado: str) -> None:
        super().__init__(f"un trabajo en {estado} esta protegido contra borrado")
        self.estado = estado


class SinProductoQueValidar(Exception):
    """Se pidio validar una linea que no tiene producto que confirmar."""


class PreviewNoPublicable(Exception):
    """Un `preview_onboarding` no se publica: no tiene acudiente. Se aprueba la
    LISTA (Catalogo), que si crea el colegio y arma el trabajo del padre."""


class NoCanonizable(Exception):
    """Solo un trabajo SIN acudiente (un preview o el canonico de una lista) se
    fija a mano como kit canonico: el de un padre lleva sus preferencias y su
    tope, y no puede servirle a otro."""


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


async def crear(
    motor: Any,
    *,
    hijos: list[dict[str, Any]],
    contacto: dict[str, Any] | None = None,
    preferencias: dict[str, Any] | None = None,
    origen: str = "colegio_grado",
    identidad: ClienteIdentidad | None = None,
    usuario_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Crea el trabajo en `encolado` y devuelve el cuerpo del 202.

    El contacto se registra en Identidad y aqui solo queda su identificador.
    Si Identidad no responde, el trabajo se crea igual con la degradacion
    anotada: perder el aviso es malo, perder el kit por no poder avisar es
    peor.

    `usuario_id` permite crear el trabajo para un acudiente YA identificado sin
    volver a llamar a Identidad: es lo que usa el poller de `lista_verificada`,
    donde el padre subio su lista hace rato y su `usuario_id` ya vive en la
    tarea. Si viene, gana sobre `contacto` (no se re-registra nada).
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
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id,
                usuario_id=usuario_id,
                estado=EstadoTrabajo.ENCOLADO.value,
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
    await conexion.execute(
        update(ETAPA)
        .where(ETAPA.c.trabajo_id == trabajo_id, ETAPA.c.nombre == nombre)
        .values(estado=estado, ms=ms, detalle=detalle or {}, terminada_en=ahora())
    )


async def _estado(conexion: Any, trabajo_id: uuid.UUID) -> str:
    valor = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    if valor is None:
        raise TrabajoNoExiste(str(trabajo_id))
    return str(valor)


async def _pasar_a(conexion: Any, trabajo_id: uuid.UUID, nuevo: str, **extra: Any) -> None:
    actual = await _estado(conexion, trabajo_id)
    if actual == nuevo:
        return
    if not puede_pasar(actual, nuevo):
        raise TransicionIlegal(actual, nuevo)
    await conexion.execute(update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(estado=nuevo, **extra))


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


def _normalizar(renglones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cada renglon a una demanda, con lo que la lista ya sabia por encima.

    El parseo lee el texto; la lista oficial, cuando existe, ya trae el tipo
    y el modo revisados por quien la cargo. Se prefiere lo de la lista porque
    es un dato curado y el parseo es una heuristica sobre texto: adivinar
    encima de un dato que ya esta es como se pierde informacion buena.
    """
    normalizados = []
    for crudo in renglones:
        demanda = parsear_renglon(crudo["texto"], cantidad=crudo.get("cantidad"))
        tipo = crudo.get("tipo_item_lista") or demanda.tipo_item
        modo = crudo.get("modo_lista") or demanda.modo_adquisicion
        normalizados.append(
            {
                **crudo,
                "tipo_item": tipo,
                "modo_adquisicion": modo,
                "cantidad": demanda.cantidad,
                "unidad_base": demanda.unidad_base,
                "url_externa": crudo.get("url_externa") or demanda.url_externa,
                "nota": demanda.nota,
                "mensaje": mensaje_para_papa(demanda),
                "busca_en_catalogo": tipo in {"util", "libro_libre"}
                and modo in {"mercado_abierto", "libro_libre"},
            }
        )
    return normalizados


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


def estado_desde_emparejamiento(emparejamiento: dict[str, Any], umbral: float) -> str:
    """Traduce el vocabulario del catalogo al `EstadoResolucion` del contrato.

    La traduccion que importa es la de `abstencion`. El catalogo se abstiene
    cuando entendio el concepto y ningun producto declara el atributo que el
    renglon exige ("block tamano oficio"), y eso es exactamente
    `HUECO_CATALOGO`: te entendi y no lo tengo. Mandarlo a `SIN_MATCH` seria
    decir "no te entendi", que es la confusion que el contrato separa a
    proposito porque solo una de las dos se puede responder con una
    alternativa.
    """
    estado = emparejamiento.get("estado")
    if estado == "reconocido":
        if not emparejamiento.get("opciones"):
            return EstadoResolucion.HUECO_CATALOGO.value
        parecido = float(emparejamiento.get("parecido") or 0.0)
        return EstadoResolucion.RESUELTO_AUTO.value if parecido >= umbral else EstadoResolucion.AMBIGUO.value
    if estado in {"hueco_catalogo", "abstencion"}:
        return EstadoResolucion.HUECO_CATALOGO.value
    return EstadoResolucion.SIN_MATCH.value


def _candidato(opcion: dict[str, Any]) -> Candidato:
    return Candidato(
        sku=opcion.get("sku") or "",
        nombre=opcion.get("nombre") or "",
        nivel=opcion.get("nivel") or "confiable",
        precio_cop=opcion.get("precio_cop"),
        producto_id=opcion.get("producto_id"),
        marca=opcion.get("marca"),
        personaje=opcion.get("personaje"),
        imagen_url=opcion.get("imagen_url"),
        unidad_base=opcion.get("unidad_base") or "unidad",
        unidades_por_empaque=int(opcion.get("unidades_por_empaque") or 1),
        atributos=dict(opcion.get("atributos") or {}),
        cumple=bool(opcion.get("cumple", True)),
    )


def _personaje_pedido(preferencias: dict[str, Any]) -> str | None:
    """El personaje que el acudiente pidio, para anclar sus 4 items al tope.

    El anclaje reordena el kit completo, asi que se toma el primer personaje
    declarado en `personaje_por_hijo`. En el caso comun (un hijo con un
    personaje) es exactamente el suyo; con varios hijos se ancla el primero,
    que es suficiente para el gesto de "poner arriba lo del personaje" sin
    reordenar de forma ambigua entre hermanos.
    """
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    for valores in por_hijo.values():
        if valores:
            return str(valores[0])
    return None


def _anclar_kits(kits: list[Any], preferencias: dict[str, Any]) -> list[Any]:
    """Sube los 4 conceptos ancla del personaje pedido al tope de cada kit.

    Post-proceso puro: no cambia totales ni que producto se eligio (NSGA-II
    queda intacto). Si no se pidio personaje, `anclar_personaje` devuelve el
    kit sin tocar.
    """
    personaje = _personaje_pedido(preferencias)
    if personaje is None:
        return kits
    return [anclar_personaje(kit, personaje) for kit in kits]


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
    for kit in kits:
        kit_id = uuid.uuid4()
        await conexion.execute(
            insert(KIT).values(
                id=kit_id,
                trabajo_id=trabajo_id,
                perfil=kit.perfil,
                total_cop=kit.total_cop,
                objetivos=kit.objetivos,
                recomendado=kit.recomendado,
                razon_recomendacion=kit.razon,
                dentro_de_presupuesto=kit.dentro_de_presupuesto,
                pesos_usados_cifrados=cifrador.cifrar_json(
                    {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
                ),
                consolidaciones=list(kit.consolidaciones),
            )
        )
        for linea in kit.lineas:
            elegido = linea.elegido
            await conexion.execute(
                insert(LINEA).values(
                    id=uuid.uuid4(),
                    kit_id=kit_id,
                    item_crudo_id=ids_item[(linea.hijo, linea.orden)],
                    producto_canonico_id=(
                        uuid.UUID(elegido.producto_id) if elegido and elegido.producto_id else None
                    ),
                    hijo_referencia=linea.hijo,
                    orden=linea.orden,
                    descripcion=linea.descripcion,
                    tipo=linea.tipo,
                    estado_resolucion=linea.estado_resolucion,
                    cantidad_pedida=linea.cantidad_pedida,
                    unidad_base=linea.unidad_base,
                    unidades_por_empaque=linea.unidades_por_empaque,
                    unidades_a_comprar=linea.unidades_a_comprar,
                    sku=elegido.sku if elegido else None,
                    nombre_producto=elegido.nombre if elegido else None,
                    marca=elegido.marca if elegido else None,
                    nivel=elegido.nivel if elegido else None,
                    personaje=elegido.personaje if elegido else None,
                    imagen_url=elegido.imagen_url if elegido else None,
                    confianza=None,
                    precio_unitario_cop=linea.precio_unitario_cop,
                    subtotal_cop=linea.subtotal_cop,
                    informativa=linea.informativa,
                    instruccion_colegio=linea.instruccion_colegio,
                    url_externa=linea.url_externa,
                    mensaje=linea.mensaje,
                    no_consolidable=linea.no_consolidable,
                    motivo_no_consolidable=linea.motivo_no_consolidable,
                    alternativas=[
                        {
                            "sku": alternativa.sku,
                            "nombre": alternativa.nombre,
                            "nivel": alternativa.nivel,
                            "precio_cop": alternativa.precio_cop,
                            "imagen_url": alternativa.imagen_url,
                        }
                        for alternativa in linea.alternativas
                    ],
                )
            )

    await _marcar_etapa(
        conexion,
        trabajo_id,
        "optimizacion",
        EstadoEtapa.OK.value,
        ms=ms,
        detalle={
            "kits": len(kits),
            "recomendado": next((k.perfil for k in kits if k.recomendado), None),
        },
    )


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

                    motivo = (
                        "resuelto desde lista verificada"
                        if candidatos
                        else "lista verificada: el concepto aun no tiene productos"
                    )
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
                            atributos_impuestos={},
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

    reloj = time.monotonic()
    kits = armar_los_tres(renglones, preferencias)
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

        kits = armar_los_tres(renglones, preferencias)
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


def lanzar(motor: Any, trabajo_id: uuid.UUID) -> asyncio.Task:
    """Arranca el procesamiento de fondo.

    Version simple y declarada: una tarea del mismo proceso. Si el servicio
    se reinicia con un trabajo en vuelo, ese trabajo se queda en
    `procesando` hasta que alguien lo reencole con
    `POST /v1/trabajos/{id}/reintentar`. Un trabajador aparte leyendo de la
    bandeja de salida lo retomaria solo, y es lo que va despues.
    """
    return asyncio.create_task(procesar(motor, trabajo_id))


async def _publicar_evento(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Deja `kits_publicados` en la bandeja, en la MISMA transaccion.

    El repartidor de Operacion (`tukit_operacion.repartidor`) lo drena y avisa al
    acudiente resolviendo su `usuario_id` desde `trabajo_pipeline`. Por eso este
    evento solo tiene sentido en un trabajo con acudiente; un preview
    (`usuario_id` NULL) no llega aca —`revisar` lo rechaza antes— para no dejar un
    evento sin destinatario que el repartidor reintente sin fin.
    """
    await conexion.execute(
        insert(BANDEJA).values(
            tipo="kits_publicados",
            agregado_tipo="trabajo_pipeline",
            agregado_id=trabajo_id,
            carga={"trabajo_id": str(trabajo_id), "publicado_en": ahora().isoformat()},
        )
    )


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

        if mostrar and cabeza.origen == "parent_apply":
            # Un puntero al canonico: no tiene kits propios. Se sigue
            # `hijos[0].canonico_trabajo_id` y se pinta el unico kit del perfil
            # elegido, con el personaje aplicado sobre las anclas.
            hijo = (list(cabeza.hijos or ()) or [{}])[0]
            canonico_id = hijo.get("canonico_trabajo_id")
            perfil = str(hijo.get("perfil") or "")
            if canonico_id and perfil:
                # ponytail: 4 llamadas de catalogo dentro de la txn de lectura
                # (SELECT puro, sin locks, un solo kit). Si molesta, resolver los
                # swaps antes de abrir la txn con una pre-lectura de cabeza.
                swaps = await _anclas_de_personaje(catalogo, hijo.get("personaje")) if catalogo else {}
                lineas, total = await _lineas_aplicadas(
                    conexion, uuid.UUID(str(canonico_id)), perfil, swaps
                )
                kits.append(
                    {
                        "perfil": perfil,
                        "total": total,
                        "objetivos": {},
                        "lineas": lineas,
                        "consolidaciones": [],
                        "informativas": sum(1 for linea in lineas if linea["informativa"]),
                    }
                )
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
                cuerpo = {
                    "perfil": kit.perfil,
                    "total": int(kit.total_cop),
                    "objetivos": dict(kit.objetivos or {}),
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
        # en el kit pero no entra a la orden.
        if linea["informativa"] or not elegido or elegido.get("precio") is None:
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
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil} sin lineas comprables")

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
    liste los trabajos (las filas `recibida`, que solo viven en el catalogo, no
    aparecen mientras dure la caida).
    """
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.origen,
            TRABAJO.c.hijos,
            TRABAJO.c.creado_en,
        )
        .where(TRABAJO.c.usuario_id == usuario_id)
        .order_by(TRABAJO.c.creado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))

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
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "creado_en": lista_subida.get("creada_en"),
                    "_orden": _a_consciente(lista_subida.get("creada_en")),
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


async def previews_de(
    motor: Any, colegio_id: str, grado: str, anio_lectivo: int
) -> list[uuid.UUID]:
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
    return (
        await conexion.execute(
            select(RESOLUCION)
            .select_from(RESOLUCION.join(ITEM, ITEM.c.id == RESOLUCION.c.item_crudo_id))
            .where(ITEM.c.trabajo_id == trabajo_id, ITEM.c.id == item_id)
        )
    ).one_or_none()


async def decidir_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    estado: str,
    sku: str | None = None,
    actor: uuid.UUID | None = None,
    motivo: str | None = None,
) -> dict[str, Any]:
    """AD-04: una persona valida el emparejamiento o lo marca sin coincidencia.

    Escribe la transicion ANTES de cambiar el estado y en la misma
    transaccion, porque una decision humana sin rastro de quien la tomo es
    justo el control sin dueno que la cola existe para no ser.
    """
    async with motor.engine.begin() as conexion:
        actual = await _resolucion_de(conexion, trabajo_id, item_id)
        if actual is None:
            raise TrabajoNoExiste(f"{trabajo_id}/{item_id}")

        candidato_id = actual.candidato_item_id
        if sku:
            elegido = await conexion.scalar(
                select(CANDIDATO.c.id).where(
                    and_(CANDIDATO.c.item_crudo_id == item_id, CANDIDATO.c.sku == sku)
                )
            )
            candidato_id = elegido

        validando = estado == EstadoResolucion.RESUELTO_AUTO.value
        if validando and candidato_id is None:
            # "Confirmar el que eligio el sistema" llega sin sku. Una linea
            # AMBIGUA no tiene candidato en la resolucion: quien eligio fue el
            # optimizador, kit por kit, y eso vive en LINEA. Se toma el candidato
            # que pusieron mas kits; sin esto, la validacion quedaba resuelta y
            # sin producto, y el CHECK `resolucion_resuelta_tiene_candidato` la
            # tumbaba con un 500.
            candidato_id = await _candidato_elegido_en_kits(conexion, trabajo_id, item_id)
        if validando and candidato_id is None:
            raise SinProductoQueValidar(f"{trabajo_id}/{item_id}")

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
                candidato_item_id=candidato_id if estado == EstadoResolucion.RESUELTO_AUTO.value else None,
                decidido_por=actor,
                decidido_en=ahora(),
            )
        )
    return {"item_id": str(item_id), "estado": estado, "sku": sku}


async def _candidato_elegido_en_kits(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> Any:
    """El candidato del item que mas kits de este trabajo pusieron en su linea."""
    return await conexion.scalar(
        select(CANDIDATO.c.id)
        .select_from(
            LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id).join(
                CANDIDATO,
                and_(CANDIDATO.c.item_crudo_id == LINEA.c.item_crudo_id, CANDIDATO.c.sku == LINEA.c.sku),
            )
        )
        .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id)
        .group_by(CANDIDATO.c.id, CANDIDATO.c.sku)
        .order_by(func.count().desc(), CANDIDATO.c.sku)
        .limit(1)
    )


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
    no por-item: `decidir_linea` solo escribe RESOLUCION y nunca toca LINEA, asi
    que el kit publicado seguia mostrando el producto del optimizador. Esta es la
    ruta de escritura que faltaba. El producto se pide al catalogo (no al
    CANDIDATO) porque un personaje puede no ser candidato del item y aun asi ser
    una eleccion valida del revisor.

    `subtotal = precio * techo(cantidad_pedida / unidades_por_empaque)`, la misma
    aritmetica del armado (optimizador._construir_linea). Recalcula KIT.total_cop.
    """
    producto = await catalogo.producto(sku)
    precio = producto.get("precio_desde")
    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(LINEA.c.id, LINEA.c.kit_id, LINEA.c.cantidad_pedida, LINEA.c.informativa)
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
            )
        )
        await _recalcular_total_kit(conexion, fila.kit_id)
    return {"trabajo_id": str(trabajo_id), "perfil": perfil, "item_id": str(item_id), "sku": sku}


async def _recalcular_total_kit(conexion: Any, kit_id: uuid.UUID) -> None:
    total = await conexion.scalar(
        select(func.coalesce(func.sum(LINEA.c.subtotal_cop), 0)).where(LINEA.c.kit_id == kit_id)
    )
    await conexion.execute(update(KIT).where(KIT.c.id == kit_id).values(total_cop=int(total or 0)))


async def revisar(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    decision: str,
    nota: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """AD-06: aprobar publica al acudiente, devolver reabre sin avisar."""
    nuevo = EstadoTrabajo.PUBLICADO.value if decision == "aprobar" else EstadoTrabajo.PROCESANDO.value
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
            await _publicar_evento(conexion, trabajo_id)
            await _fijar_canonico(conexion, trabajo_id)

    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}


async def _fijar_canonico(conexion: Any, trabajo_id: uuid.UUID) -> None:
    """Al publicar, apunta la cache canonica de (colegio, grado, anio) a este trabajo.

    Solo cuando el trabajo tiene UNA identidad de grado clara: un solo hijo con
    colegio y grado (el caso de onboarding y de la ruta de acudiente por grado).
    Un trabajo multi-hogar, o sin colegio/grado, no define una cache de grado y
    se deja sin puntero —publicar igual funciona, solo no se cachea—.

    Publicar de nuevo para el mismo grado REEMPLAZA el puntero (delete + insert
    sobre la llave unica): una sola cache bendita por grado.
    """
    fila = (
        await conexion.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    ).one_or_none()
    hijos = list(fila.hijos or ()) if fila else []
    if len(hijos) != 1:
        return
    hijo = hijos[0]
    colegio_id = str(hijo.get("colegio_id") or "")
    grado = str(hijo.get("grado") or "")
    # Mismo anio bajo el que se construyeron los kits (ver `procesar`): si el
    # hijo no lo trajo, se cachea bajo el de omision para que la busqueda por
    # grado en /empezar caiga en la misma fila.
    anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
    if not (colegio_id and grado):
        return

    # Reemplaza el puntero del grado: la cache es una sola. No es un upsert de
    # ON CONFLICT para no atarse al dialecto —delete+insert corre igual en
    # SQLite (pruebas) y en Postgres (real)—.
    await conexion.execute(
        delete(KIT_CANONICO).where(
            KIT_CANONICO.c.colegio_id == colegio_id,
            KIT_CANONICO.c.grado == grado,
            KIT_CANONICO.c.anio_lectivo == anio,
        )
    )
    await conexion.execute(
        insert(KIT_CANONICO).values(
            id=uuid.uuid4(),
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio,
            trabajo_id=trabajo_id,
        )
    )


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
    fila = (
        await conexion.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))
    ).one_or_none()
    identidad = _identidad_de_grado(fila.hijos if fila else None)
    if identidad and identidad[3]:
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


async def grados_canonicos(motor: Any, *, colegio_id: str | None = None) -> list[dict[str, Any]]:
    """Los (colegio, grado, anio) que ya tienen cache bendita, para el selector.

    Es lo que `/empezar` lista en vez de pedir un PDF: un grado que aparece aqui
    se puede aplicar al vuelo (ruta rapida); uno que no, entra al pipeline.
    """
    consulta = select(
        KIT_CANONICO.c.colegio_id,
        KIT_CANONICO.c.grado,
        KIT_CANONICO.c.anio_lectivo,
        KIT_CANONICO.c.trabajo_id,
    ).order_by(KIT_CANONICO.c.colegio_id, KIT_CANONICO.c.grado)
    if colegio_id:
        consulta = consulta.where(KIT_CANONICO.c.colegio_id == colegio_id)
    async with motor.engine.begin() as conexion:
        filas = await conexion.execute(consulta)
    return [
        {
            "colegio_id": f.colegio_id,
            "grado": f.grado,
            "anio_lectivo": int(f.anio_lectivo),
            "trabajo_id": str(f.trabajo_id),
        }
        for f in filas
    ]


async def _anclas_de_personaje(
    catalogo: ClienteCatalogo, personaje: str | None
) -> dict[str, dict[str, Any]]:
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

        lineas_frias, total = await _lineas_aplicadas(
            conexion, canonico.trabajo_id, perfil, swaps
        )

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
