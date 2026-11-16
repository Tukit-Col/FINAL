"""El poller de `lista_verificada`: arma el kit del padre que estaba esperando.

Cuando un administrador aprueba una version que un acudiente habia subido, el
Catalogo NO llama a Inteligencia —esa arista cerraria un ciclo en el grafo de
dependencias (inteligencia->catalogo, nunca al reves)—: escribe un evento
`lista_verificada` en su bandeja de salida. Este proceso lo drena y hace lo que
el Catalogo no puede: crea un trabajo de RUTA RAPIDA para ese padre, con las
preferencias que dejo en el paso 3, y lo procesa. Al terminar, el pipeline deja
`kits_publicados` en la bandeja de Inteligencia y el repartidor de Operacion le
envia el correo con el enlace de pre-compra.

    python -m tukit_inteligencia.poller          # una pasada
    python -m tukit_inteligencia.poller --seguir  # bucle

**Con RabbitMQ** (`RABBITMQ_URL`, ADR 0046) no sondea la bandeja del Catalogo:
consume la cola `inteligencia.listas`, a la que el publicador del Catalogo lleva
los dos eventos, y no abre ningun motor a esa base. La entrega es al menos una
vez, asi que cada evento se anota en `evento_procesado` por origen e id. Para
`lista_verificada` la marca entra en la misma transaccion que crea el trabajo:
un evento repetido no arma un segundo kit aunque el proceso caiga a mitad.

**La unica excepcion a la frontera de bases**, y solo sin broker, igual que el repartidor: se abre
un motor de LECTURA/marcado a la base del Catalogo para drenar su bandeja. El
nombre de esa base NO se escribe aqui: `url_desde_entorno` lo deriva DENTRO de
la libreria a partir del nombre del servicio (regla 3). El trabajo se crea en la
base propia de Inteligencia con `trabajos.crear`, que es lo unico que este
servicio escribe.

**Una caida no lo mata** (ADR 0041). El bucle corre sobre `bucle_resiliente`:
si Postgres no responde, espera y reintenta la pasada, y cada pasada abre sus
motores de nuevo. Un error de programacion sigue terminando el proceso.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.config import url_desde_entorno
from tukit_comun.consumidor import Consumidor, RegistroEnTabla, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.topologia import LISTAS

from . import apodos_subida, trabajos
from .remoto import ClienteCatalogo

# El unico tipo de evento que este poller atiende. La bandeja del Catalogo
# lleva otros (ninguno hoy), y un tipo desconocido se marca publicado sin
# actuar, para no reprocesarlo en cada pasada.
_TIPO = "lista_verificada"
# Toda version aprobada, con o sin padre esperando: arma los kits canonicos del
# grado para que el proximo acudiente sin tope los reciba sin re-optimizar.
_TIPO_CANONICO = "lista_aprobada"


@dataclass
class Poller:
    """Drena la bandeja del Catalogo y crea el kit de ruta rapida del padre.

    Los motores y el catalogo se inyectan para poder probar sin Postgres ni
    red; en produccion salen del entorno. `motor_inteligencia` es la base
    propia (donde se crea el trabajo); `motor_catalogo` es la ajena (de donde
    se drena la bandeja, la excepcion outbox declarada); con RabbitMQ va en
    `None` y los eventos llegan a `manejar`.
    """

    motor_inteligencia: Any
    motor_catalogo: AsyncEngine | None
    catalogo: ClienteCatalogo

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos kits arranco con exito.

        El drenar/SKIP LOCKED/marcar-publicado vive en `tukit_comun.bandeja`
        (ADR 0022); aqui solo se aportan los `manejar` de `lista_verificada` y de
        `lista_aprobada`. Se drena un tipo a la vez y no la bandeja entera: lleva
        tambien eventos de otros consumidores (el poller de Identidad), y
        drenarlos aqui los marcaria publicados sin que nadie los atienda."""
        if self.motor_catalogo is None:
            raise ValueError("sin la bandeja del Catalogo no hay pasada: con RabbitMQ se usa `manejar`")
        arrancados = await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)
        arrancados += await drenar(
            self.motor_catalogo, self._procesar_canonico, tipo=_TIPO_CANONICO, limite=limite
        )
        return arrancados

    async def manejar(self, evento: Evento) -> Resultado:
        """Un evento que llega por la cola `inteligencia.listas` (ADR 0046).

        El `Evento` tiene la forma de una fila de la bandeja, asi que el manejo
        es el mismo. `lista_verificada` lleva su origen e id hasta `crear`, que
        los anota con el trabajo; `lista_aprobada` ya es idempotente (compara la
        version con la del canonico vigente) y lo anota el consumidor."""
        if evento.tipo == _TIPO:
            return await self._procesar(None, evento, evento=(evento.origen, evento.id))
        if evento.tipo == _TIPO_CANONICO:
            return await self._procesar_canonico(None, evento)
        return Resultado.OMITIR

    async def _procesar(
        self, conexion: Any, fila: Any, *, evento: tuple[str, int] | None = None
    ) -> Resultado:
        carga = fila.carga or {}
        colegio_id = carga.get("colegio_id")
        grado = carga.get("grado")
        contacto = carga.get("contacto_referencia")
        # Sin colegio o grado no hay como armar un kit de grado: OMITIR lo marca
        # publicado para no reintentarlo en vano (no es un fallo del poller, es
        # un evento que no le sirve a nadie).
        if not colegio_id or not grado:
            return Resultado.OMITIR

        # `contacto_referencia` decide el origen del trabajo:
        #   - CON padre: `usuario_id` real + origen `lista_verificada`. El kit es
        #     de ese padre; el pipeline lo publica directo y el repartidor le
        #     avisa (la revision fue sobre la LISTA, no hay segunda cola).
        #   - SIN padre (onboarding/colegio): anonimo + origen `colegio_grado`.
        #     Entra a la cola de revision (`espera_revision`); al aprobarlo ahi
        #     queda como kit CANONICO del grado —la cache que /empezar y el panel
        #     NSGA del colegio consultan—. Aprobar la LISTA y aprobar el TRABAJO
        #     sobre ella son los dos pasos que el flujo pide, en ese orden.
        usuario_id: uuid.UUID | None = None
        origen = "colegio_grado"
        if contacto:
            try:
                usuario_id = uuid.UUID(str(contacto))
                origen = "lista_verificada"
            except (ValueError, TypeError):
                # Contacto presente pero ilegible: se degrada a kit de colegio en
                # vez de descartar el evento (perder el kito del grado es peor).
                usuario_id = None
                origen = "colegio_grado"

        anio = carga.get("anio_lectivo")
        # La referencia REAL del hijo que subio la lista (`hijo-2`...): es la
        # clave con la que el formulario guardo su personaje en
        # `personaje_por_hijo`, asi que el Fan casa por clave exacta. Los
        # eventos que ya estaban en la cola antes de que el Catalogo la
        # reenviara no la traen: esos caen en `hijo-1`, como siempre.
        referencias = [str(r) for r in carga.get("referencias") or () if r]
        referencia = referencias[0] if referencias else "hijo-1"
        hijo: dict[str, Any] = {"referencia": referencia, "colegio_id": str(colegio_id), "grado": grado}
        if anio is not None:
            hijo["anio_lectivo"] = anio
        # El `version_id` (el agregado del evento) queda en el trabajo para poder
        # volver de una lista subida al trabajo que engendro: es lo que deja
        # "Mis solicitudes" unir la lista aprobada con su trabajo en una sola
        # fila, en vez de mostrar dos. La carga no lo trae; el agregado si.
        hijo["version_id"] = str(fila.agregado_id)
        # El apodo que el acudiente dio al subir la lista (guardado aqui, no en el
        # Catalogo): rotula el kit sin tener que adivinarlo por colegio y grado.
        # Se lee y se borra; si el armado falla, se reintenta con el evento y el
        # kit sale sin apodo antes que perderse el kit.
        async with self.motor_inteligencia.engine.begin() as conexion:
            apodos = await apodos_subida.tomar(conexion, str(fila.agregado_id))
        if apodos.get(referencia):
            hijo["apodo"] = apodos[referencia]

        # Las preferencias son las del paso 3 que el Catalogo guardo y reenvio en
        # la carga; {} para el kit del colegio (se arma con las preferencias base).
        try:
            respuesta = await trabajos.crear(
                self.motor_inteligencia,
                hijos=[hijo],
                preferencias=carga.get("preferencias") or {},
                origen=origen,
                usuario_id=usuario_id,
                en_proceso=True,
                evento=evento,
            )
        except trabajos.EventoRepetido:
            # Solo con broker: otra entrega del mismo evento ya creo su trabajo.
            return Resultado.OMITIR
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])

        # El trabajo nace `procesando` (`en_proceso`): este poller lo procesa
        # aqui mismo y el trabajador durable no lo reclama. `drenar` marcara el
        # evento publicado al devolver HECHO (dentro de la misma transaccion de
        # la pasada). Si el proceso muere durante el pipeline, el trabajador lo
        # retoma como colgado y el evento no se reprocesa —no se arma un segundo
        # kit para el mismo padre—.

        # La lista esta revisada: `procesar` toma la ruta rapida (sin Gemini,
        # con NSGA-II sobre los candidatos curados). El destino del trabajo
        # depende del origen: `lista_verificada` se publica directo y deja
        # `kits_publicados` para que el repartidor avise al padre; `colegio_grado`
        # queda en `espera_revision` para que un admin lo apruebe en la cola y
        # ahi se fije como canonico del grado.
        #
        # HECHO marca el evento publicado (en la misma transaccion de la pasada):
        # el trabajo ya es durable en `encolado` y `procesar` no levanta ante un
        # fallo de dependencia —lo deja `fallido` y reintentable por su estado—,
        # asi que el evento nunca se reprocesa y no se arma un segundo kit para
        # el mismo padre.
        await trabajos.procesar(self.motor_inteligencia, trabajo_id, catalogo=self.catalogo)
        return Resultado.HECHO

    async def _procesar_canonico(self, conexion: Any, fila: Any) -> Resultado:
        """Arma los kits canonicos de la version aprobada y los fija.

        Sin acudiente y sin preferencias: son los kits neutros que la ruta rapida
        le aplica a cualquiera (Ahorrador y Premium, ADR 0030). Si la version ya
        tiene canonico —el admin aprobo desde el preview y fijo esos kits— no se
        vuelve a optimizar.
        """
        carga = fila.carga or {}
        colegio_id = carga.get("colegio_id")
        grado = carga.get("grado")
        if not colegio_id or not grado:
            return Resultado.OMITIR
        anio = int(carga.get("anio_lectivo") or trabajos.ANIO_LECTIVO_POR_OMISION)
        version = str(fila.agregado_id)

        async with self.motor_inteligencia.engine.begin() as propia:
            ya = await trabajos.version_canonica(propia, str(colegio_id), grado, anio)
        if ya == version:
            return Resultado.OMITIR

        await armar_canonico(self.motor_inteligencia, self.catalogo, str(colegio_id), grado, anio, version)
        return Resultado.HECHO


async def armar_canonico(
    motor_inteligencia: Any,
    catalogo: Any,
    colegio_id: str,
    grado: str,
    anio: int,
    version: str,
    *,
    regenera: bool = False,
) -> uuid.UUID:
    """Arma los kits canonicos de una version y los publica como vigentes del grado."""
    respuesta = await trabajos.crear(
        motor_inteligencia,
        hijos=[
            {
                "referencia": "canonico",
                "colegio_id": colegio_id,
                "grado": grado,
                "anio_lectivo": anio,
                "version_id": version,
                **({"regenera": True} if regenera else {}),
            }
        ],
        preferencias={},
        origen=trabajos.ORIGEN_CANONICO,
        en_proceso=True,
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    await trabajos.procesar(motor_inteligencia, trabajo_id, catalogo=catalogo)
    return trabajo_id


async def regenerar_canonicos(motor_inteligencia: Any, catalogo: Any) -> tuple[int, list[str]]:
    """Vuelve a armar los kits canonicos que salieron del armado automatico.

    El poller no rearma una version que ya tiene canonico, y esta bien: aprobar
    dos veces no debe costar dos optimizaciones. Pero cuando cambia COMO se
    arma (el filtro por atributos, juntar herramientas), los kits publicados se
    quedan con la logica vieja. Esto los rearma con la misma version de lista.

    Solo los de origen `canonico_lista`. Los que un admin aprobo desde la
    previsualizacion, o los que corrigio con «Editar kits», pueden tener
    lineas elegidas a mano, y rearmarlos las borraria: se saltan y se
    devuelven para que una persona decida. Los kits anteriores siguen
    publicados para el acudiente que ya los tenia.
    """
    from sqlalchemy import select

    async with motor_inteligencia.engine.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(
                    trabajos.KIT_CANONICO.c.colegio_id,
                    trabajos.KIT_CANONICO.c.grado,
                    trabajos.KIT_CANONICO.c.anio_lectivo,
                    trabajos.TRABAJO.c.origen,
                    trabajos.TRABAJO.c.hijos,
                ).select_from(
                    trabajos.KIT_CANONICO.join(
                        trabajos.TRABAJO, trabajos.TRABAJO.c.id == trabajos.KIT_CANONICO.c.trabajo_id
                    )
                )
            )
        )
    rearmados = 0
    saltados: list[str] = []
    fallidos: list[str] = []
    for f in filas:
        hijo = next(iter(f.hijos or ()), {})
        nombre = f"{f.colegio_id[:8]} {f.grado} ({f.origen})"
        if f.origen != trabajos.ORIGEN_CANONICO or hijo.get("basado_en") or not hijo.get("version_id"):
            saltados.append(nombre)
            continue
        # La version se relee justo antes de rearmar, no se toma de la lista leida
        # al empezar. Mientras esto recorre los 18 grados, el poller puede fijar
        # el canonico de una version nueva (la que deja `importar`), y rearmar
        # con la version leida al principio lo pisaba con la vieja: le paso a
        # Decimo y Once el 2026-10-12.
        async with motor_inteligencia.engine.begin() as conexion:
            version = await trabajos.version_canonica(
                conexion, f.colegio_id, f.grado, int(f.anio_lectivo)
            ) or str(hijo["version_id"])
        trabajo_id = await armar_canonico(
            motor_inteligencia,
            catalogo,
            f.colegio_id,
            f.grado,
            int(f.anio_lectivo),
            str(version),
            regenera=True,
        )
        async with motor_inteligencia.engine.begin() as conexion:
            estado = await conexion.scalar(
                select(trabajos.TRABAJO.c.estado).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        if estado != "publicado":
            fallidos.append(f"{nombre}: {estado}")
            continue
        rearmados += 1
        print(f"[canonicos] rearmado {nombre}")
    for fallo in fallidos:
        print(f"[canonicos] NO se rearmo {fallo}")
    return rearmados, saltados


def _motor_lectura(servicio: str) -> AsyncEngine:
    """Motor a la base de un servicio ajeno (aqui, el Catalogo).

    El nombre de la base lo deriva `url_desde_entorno` DENTRO de la libreria a
    partir del nombre del servicio; este archivo nunca escribe el nombre de la
    base ajena, que es lo que mantiene verde la regla 3.
    """
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez(
    *,
    motor_inteligencia: MotorServicio | None = None,
    motor_catalogo: AsyncEngine | None = None,
    catalogo: Any = None,
) -> int:
    """Una pasada sobre la bandeja del Catalogo. Para el cron o el arranque.

    Sin argumentos abre sus motores y su cliente, y los cierra al terminar. Los
    que se le pasan (las pruebas) son de quien los paso: no los cierra."""
    propio_inteligencia = motor_inteligencia is None
    propio_catalogo = motor_catalogo is None
    motor_inteligencia = motor_inteligencia or crear_motor("inteligencia")
    motor_catalogo = motor_catalogo or _motor_lectura("catalogo")
    try:
        poller = Poller(
            motor_inteligencia=motor_inteligencia,
            motor_catalogo=motor_catalogo,
            catalogo=catalogo or ClienteCatalogo(),
        )
        return await poller.pasada()
    finally:
        if propio_catalogo:
            await motor_catalogo.dispose()
        if propio_inteligencia:
            await motor_inteligencia.cerrar()


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    """Con RabbitMQ (ADR 0046): consume `inteligencia.listas` en vez de sondear.

    Solo abre la base de Inteligencia, donde tambien vive `evento_procesado`.
    Sin `seguir`, procesa lo que hay en la cola y vuelve; con `seguir`, escucha
    sobre `bucle_resiliente`."""
    motor_inteligencia = crear_motor("inteligencia")
    poller = Poller(motor_inteligencia=motor_inteligencia, motor_catalogo=None, catalogo=ClienteCatalogo())
    try:
        return await consumir(
            url,
            Consumidor(
                cola=LISTAS, manejar=poller.manejar, registro=RegistroEnTabla(motor_inteligencia.engine)
            ),
            seguir=seguir,
            proceso="inteligencia-poller",
            intervalo=intervalo,
        )
    finally:
        await motor_inteligencia.cerrar()


async def _regenerar() -> tuple[int, list[str]]:
    motor_inteligencia = crear_motor("inteligencia")
    try:
        return await regenerar_canonicos(motor_inteligencia, ClienteCatalogo())
    finally:
        await motor_inteligencia.cerrar()


async def correr_en_bucle(
    intervalo: float, *, dormir: Callable[[float], Awaitable[None]] | None = None, **dependencias: Any
) -> None:
    """`correr_una_vez` en bucle resiliente; `dependencias` llegan a cada pasada."""

    async def _vuelta() -> None:
        arrancados = await correr_una_vez(**dependencias)
        if arrancados:
            print(f"[poller] kits de ruta rapida arrancados: {arrancados}")

    await bucle_resiliente(
        _vuelta, intervalo=intervalo, proceso="inteligencia-poller", dormir=dormir or asyncio.sleep
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `lista_verificada` del Catalogo y arma el kit del padre que esperaba."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    analizador.add_argument(
        "--regenerar-canonicos",
        action="store_true",
        help="Rearma los kits canonicos automaticos con la logica actual (salta los editados a mano).",
    )
    argumentos = analizador.parse_args(argv)
    configurar_registro("inteligencia-poller")

    if argumentos.regenerar_canonicos:
        rearmados, saltados = asyncio.run(_regenerar())
        print(f"[canonicos] rearmados: {rearmados}")
        for nombre in saltados:
            print(f"[canonicos] saltado (puede tener lineas elegidas a mano): {nombre}")
        return 0

    url = url_broker()
    if url:
        procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
        if not argumentos.seguir:
            print(f"[poller] mensajes de {LISTAS.nombre}: {procesados}")
        return 0
    if argumentos.seguir:
        asyncio.run(correr_en_bucle(argumentos.intervalo))
    else:
        arrancados = asyncio.run(correr_una_vez())
        print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
