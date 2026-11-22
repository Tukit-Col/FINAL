"""Creacion del trabajo y las etapas del pipeline: percepcion, resolucion, optimizacion y cierre."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import delete, insert, select, update
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.consumidor import marcar_procesado

from ..dominio.pipeline import (
    _anclar_kits,
    _candidato,
    _normalizar,
    estado_desde_emparejamiento,
    inyectar_personaje_fan,
    personajes_de_los_hijos,
)
from ..modelos import (
    EstadoEtapa,
    EstadoResolucion,
    EstadoTrabajo,
)
from ..modelos.trabajo import ETAPAS
from ..optimizador import (
    Candidato,
    Renglon,
    armar_los_tres,
)
from ..parseo import BUSCA_EN_CATALOGO, Demanda, mensaje_para_papa
from ..remoto import ClienteCatalogo, ClienteIdentidad, RemotoCaido
from ..repositorios.trabajos import RepoTrabajos, TrabajoNoExiste
from .anclas import anclas_por_hijo
from .base import (
    ANIO_LECTIVO_POR_OMISION,
    CANDIDATO,
    ETAPA,
    ITEM,
    KIT,
    ORIGEN_CANONICO,
    RESOLUCION,
    TRABAJO,
    TRANSICION,
    _avisar_encolado,
    _estado,
    _pasar_a,
    _publicar_evento,
    ahora,
    autopublicar,
    tau,
)
from .revision import _cerrar_canonico_de_lista


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
                        atributos_impuestos=dict(item.get("atributos_impuestos") or {}),
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
    swaps = await anclas_por_hijo(
        catalogo, personajes_de_los_hijos(preferencias, [r.hijo for r in renglones])
    )

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
                    atributos_impuestos=dict((respuesta or {}).get("atributos_impuestos") or {}),
                )
            )

        swaps = await anclas_por_hijo(
            catalogo, personajes_de_los_hijos(preferencias, [r.hijo for r in renglones])
        )
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
