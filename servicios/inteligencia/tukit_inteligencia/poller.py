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

**La unica excepcion a la frontera de bases**, igual que el repartidor: se abre
un motor de LECTURA/marcado a la base del Catalogo para drenar su bandeja. El
nombre de esa base NO se escribe aqui: `url_desde_entorno` lo deriva DENTRO de
la libreria a partir del nombre del servicio (regla 3). El trabajo se crea en la
base propia de Inteligencia con `trabajos.crear`, que es lo unico que este
servicio escribe.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
from tukit_comun.bd import crear_motor
from tukit_comun.config import url_desde_entorno

from . import trabajos
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
    se drena la bandeja, la excepcion outbox declarada).
    """

    motor_inteligencia: Any
    motor_catalogo: AsyncEngine
    catalogo: ClienteCatalogo

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos kits arranco con exito.

        El drenar/SKIP LOCKED/marcar-publicado vive en `tukit_comun.bandeja`
        (ADR 0022); aqui solo se aportan los `manejar` de `lista_verificada` y de
        `lista_aprobada`. Se drena un tipo a la vez y no la bandeja entera: lleva
        tambien eventos de otros consumidores (el poller de Identidad), y
        drenarlos aqui los marcaria publicados sin que nadie los atienda."""
        arrancados = await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)
        arrancados += await drenar(
            self.motor_catalogo, self._procesar_canonico, tipo=_TIPO_CANONICO, limite=limite
        )
        return arrancados

    async def _procesar(self, conexion: Any, fila: Any) -> Resultado:
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
        hijo: dict[str, Any] = {"referencia": "hijo-1", "colegio_id": str(colegio_id), "grado": grado}
        if anio is not None:
            hijo["anio_lectivo"] = anio
        # El `version_id` (el agregado del evento) queda en el trabajo para poder
        # volver de una lista subida al trabajo que engendro: es lo que deja
        # "Mis solicitudes" unir la lista aprobada con su trabajo en una sola
        # fila, en vez de mostrar dos. La carga no lo trae; el agregado si.
        hijo["version_id"] = str(fila.agregado_id)

        # Las preferencias son las del paso 3 que el Catalogo guardo y reenvio en
        # la carga; {} para el kit del colegio (se arma con las preferencias base).
        respuesta = await trabajos.crear(
            self.motor_inteligencia,
            hijos=[hijo],
            preferencias=carga.get("preferencias") or {},
            origen=origen,
            usuario_id=usuario_id,
            en_proceso=True,
        )
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

        respuesta = await trabajos.crear(
            self.motor_inteligencia,
            hijos=[
                {
                    "referencia": "canonico",
                    "colegio_id": str(colegio_id),
                    "grado": grado,
                    "anio_lectivo": anio,
                    "version_id": version,
                }
            ],
            preferencias={},
            origen=trabajos.ORIGEN_CANONICO,
            en_proceso=True,
        )
        await trabajos.procesar(
            self.motor_inteligencia, uuid.UUID(respuesta["trabajo_id"]), catalogo=self.catalogo
        )
        return Resultado.HECHO


def _motor_lectura(servicio: str) -> AsyncEngine:
    """Motor a la base de un servicio ajeno (aqui, el Catalogo).

    El nombre de la base lo deriva `url_desde_entorno` DENTRO de la libreria a
    partir del nombre del servicio; este archivo nunca escribe el nombre de la
    base ajena, que es lo que mantiene verde la regla 3.
    """
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez() -> int:
    """Una pasada sobre la bandeja del Catalogo. Para el cron o el arranque."""
    motor_inteligencia = crear_motor("inteligencia")
    motor_catalogo = _motor_lectura("catalogo")
    catalogo = ClienteCatalogo()
    try:
        poller = Poller(
            motor_inteligencia=motor_inteligencia,
            motor_catalogo=motor_catalogo,
            catalogo=catalogo,
        )
        return await poller.pasada()
    finally:
        await motor_catalogo.dispose()
        await motor_inteligencia.cerrar()


async def _bucle(intervalo: float) -> None:
    while True:
        arrancados = await correr_una_vez()
        if arrancados:
            print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
        await asyncio.sleep(intervalo)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `lista_verificada` del Catalogo y arma el kit del padre que esperaba."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        arrancados = asyncio.run(correr_una_vez())
        print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
