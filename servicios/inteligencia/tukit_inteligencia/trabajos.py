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
from .optimizador import Candidato, Renglon, anclar_personaje, armar_los_tres
from .parseo import mensaje_para_papa, parsear_renglon
from .remoto import ClienteCatalogo, ClienteIdentidad, RemotoCaido

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
ETAPA = Base.metadata.tables["etapa_trabajo"]
ITEM = Base.metadata.tables["item_crudo"]
CANDIDATO = Base.metadata.tables["candidato_item"]
RESOLUCION = Base.metadata.tables["resolucion_item"]
TRANSICION = Base.metadata.tables["transicion_resolucion"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]
BANDEJA = Base.metadata.tables["bandeja_salida"]

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


class TransicionIlegal(Exception):
    def __init__(self, actual: str, pedida: str) -> None:
        super().__init__(f"no se puede pasar de {actual} a {pedida}")
        self.actual = actual
        self.pedida = pedida


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
) -> dict[str, Any]:
    """Crea el trabajo en `encolado` y devuelve el cuerpo del 202.

    El contacto se registra en Identidad y aqui solo queda su identificador.
    Si Identidad no responde, el trabajo se crea igual con la degradacion
    anotada: perder el aviso es malo, perder el kit por no poder avisar es
    peor.
    """
    degradaciones: list[dict[str, Any]] = []
    usuario_id: uuid.UUID | None = None
    if contacto and contacto.get("correo"):
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


async def _finalizar(motor: Any, trabajo_id: uuid.UUID) -> str:
    """El cierre comun: autopublicar o dejar en espera de revision.

    No cambia con la ruta: la lista verificada NO crea una aprobacion nueva ni
    toca `revisada_en`; solo decide, como siempre, si la valvula de desarrollo
    publica directo o si el kit espera a una persona.
    """
    async with motor.engine.begin() as conexion:
        if autopublicar():
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
                surtible = item.get("concepto_codigo") is not None

                await conexion.execute(
                    insert(ITEM).values(
                        id=item_id,
                        trabajo_id=trabajo_id,
                        hijo_referencia=hijo,
                        orden=orden,
                        texto=item["texto_original"],
                        cantidad=int(item.get("cantidad") or 1),
                        unidad_base=(candidatos[0].unidad_base if candidatos else "unidad"),
                        tipo_item=item.get("tipo_item") or "util",
                        modo_adquisicion=item.get("modo_adquisicion") or "mercado_abierto",
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

                    resolucion_id = uuid.uuid4()
                    await conexion.execute(
                        insert(RESOLUCION).values(
                            id=resolucion_id,
                            item_crudo_id=item_id,
                            estado=EstadoResolucion.RESUELTO_AUTO.value,
                            concepto_codigo=item.get("concepto_codigo"),
                            concepto_nombre=item.get("concepto_nombre"),
                            parecido=1.0,
                            candidato_item_id=elegido_id,
                            atributos_impuestos={},
                            motivo="resuelto desde lista verificada",
                        )
                    )
                    await conexion.execute(
                        insert(TRANSICION).values(
                            id=uuid.uuid4(),
                            resolucion_item_id=resolucion_id,
                            estado_anterior=None,
                            estado_nuevo=EstadoResolucion.RESUELTO_AUTO.value,
                            motivo="resuelto desde lista verificada",
                        )
                    )

                renglones.append(
                    Renglon(
                        hijo=hijo,
                        orden=orden,
                        texto=item["texto_original"],
                        tipo_item=item.get("tipo_item") or "util",
                        modo_adquisicion=item.get("modo_adquisicion") or "mercado_abierto",
                        cantidad=int(item.get("cantidad") or 1),
                        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
                        unidad_base=(candidatos[0].unidad_base if candidatos else "unidad"),
                        concepto_codigo=item.get("concepto_codigo"),
                        concepto_nombre=item.get("concepto_nombre"),
                        parecido=1.0,
                        candidatos=candidatos,
                        mensaje=None,
                        instruccion_colegio=item.get("instruccion_colegio"),
                        url_externa=item.get("url_externa"),
                        nota=None,
                    )
                )

        ms = int((time.monotonic() - reloj) * 1000)
        fuente = {"fuente": "lista_verificada"}
        listas_detalle = {
            "fuente": "lista_verificada",
            "listas": [
                {"hijo": e["hijo"], "version_id": str(e["version_id"])} for e in encontradas
            ],
        }
        await _marcar_etapa(
            conexion, trabajo_id, "percepcion", EstadoEtapa.OK.value, ms=ms, detalle=listas_detalle
        )
        await _marcar_etapa(
            conexion, trabajo_id, "normalizacion", EstadoEtapa.OK.value, ms=0,
            detalle={**fuente, "renglones": len(renglones)},
        )
        resueltos = sum(1 for r in renglones if r.concepto_codigo is not None)
        await _marcar_etapa(
            conexion, trabajo_id, "resolucion", EstadoEtapa.OK.value, ms=0,
            detalle={**fuente, "resueltos": resueltos, "a_revision": 0},
        )

    reloj = time.monotonic()
    kits = armar_los_tres(renglones, preferencias)
    kits = _anclar_kits(kits, preferencias)
    ms = int((time.monotonic() - reloj) * 1000)

    async with motor.engine.begin() as conexion:
        await _escribir_kits(conexion, trabajo_id, kits, ids_item, preferencias, cifrador, ms=ms)

    return await _finalizar(motor, trabajo_id)


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
                select(TRABAJO.c.estado, TRABAJO.c.hijos, TRABAJO.c.preferencias_cifradas).where(
                    TRABAJO.c.id == trabajo_id
                )
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
                motor, trabajo_id, catalogo, encontradas, preferencias, cifrador
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
            respuestas = await catalogo.emparejar([r["texto"] for r in buscables])
            for renglon, respuesta in zip(buscables, respuestas, strict=False):
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

        return await _finalizar(motor, trabajo_id)

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

    Hoy nadie lo recoge: el repartidor y el consumidor de Operacion no
    existen todavia, asi que el aviso al acudiente no sale. Se escribe igual
    porque la mitad transaccional es la que no se puede agregar despues sin
    reescribir el flujo, y porque el dia que exista el repartidor los
    trabajos ya publicados tendran su evento esperando.
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


async def ver(motor: Any, trabajo_id: uuid.UUID, *, incluir_kits: bool | None = None) -> dict[str, Any]:
    """El cuerpo de `GET /v1/trabajos/{id}`.

    Mientras el estado no sea `publicado`, `kits` va vacio: el acudiente
    nunca ve un kit sin revisar, y esa es la razon de ser de
    `espera_revision`. Admin usa el mismo lector con `incluir_kits=True`,
    porque su trabajo es justamente mirar lo que todavia no se publica.
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

        if mostrar:
            for kit in await conexion.execute(
                select(KIT).where(KIT.c.trabajo_id == trabajo_id).order_by(KIT.c.total_cop)
            ):
                lineas = [
                    _linea_publica(f)
                    for f in await conexion.execute(
                        select(LINEA)
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
    }


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
                "hijos": len(list(f.hijos or ())),
                "lineas_a_revisar": int(f.dudosos),
            }
            for f in filas
        ]
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "trabajos": datos}


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

    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}
