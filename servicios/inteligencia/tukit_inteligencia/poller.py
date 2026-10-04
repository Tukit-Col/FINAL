"""El poller de `lista_verificada`: arma el kit del padre que estaba esperando.

Cuando un administrador aprueba una version que un acudiente habia subido, el
Catalogo NO llama a Inteligencia —esa arista cerraria un ciclo en el grafo de
dependencias (inteligencia->catalogo, nunca al reves)—: escribe un evento
`lista_verificada` en su bandeja de salida. Este proceso lo drena y hace lo que
el Catalogo no puede: crea un trabajo de RUTA RAPIDA para ese padre, con las
preferencias que dejo en el paso 3, y lo procesa. Al terminar, el pipeline deja
`kits_publicados` en la bandeja de Inteligencia y el repartidor de Operacion le
envia el correo con el enlace de pre-compra.

Antes de crear nada busca la vista previa que el admin armo y ajusto sobre ESA
version: si la hay y sigue valiendo, la promueve a kit del colegio y grado en vez
de armar otro trabajo que perderia los ajustes (`trabajos.promover_vista_previa`).
Con padre de un solo hijo, su kit sale de ese kit del grado con su nivel y su
personaje, como en la ruta rapida. Al terminar, borra las vistas previas que
quedaron de la version (`trabajos.descartar_previas_de_version`).

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
        (ADR 0022); aqui solo se aporta el `manejar` de `lista_verificada`."""
        return await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)

    async def _procesar(self, conexion: Any, fila: Any) -> Resultado:
        resultado = await self._armar(fila)
        if resultado is Resultado.HECHO:
            # La version ya no esta pendiente: lo que quede de sus vistas previas
            # (la vieja, la que no se pudo promover) ya no tiene lista que
            # previsualizar. Solo en HECHO: al REINTENTAR la promocion la necesita.
            await trabajos.descartar_previas_de_version(self.motor_inteligencia, fila.agregado_id)
        return resultado

    async def _armar(self, fila: Any) -> Resultado:
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
        #     Si el admin dejo una vista previa ajustada de esta version, se
        #     promueve (abajo). Si no, se arma un trabajo nuevo que entra a la
        #     cola (`espera_revision`); al aprobarlo ahi queda como kit CANONICO
        #     del grado —la cache que /empezar y el panel NSGA del colegio
        #     consultan—.
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
        # `referencias_hijo` no es una preferencia: es la nota de `subir_listas`
        # de que hijos comparten esta version, y no viaja al trabajo.
        preferencias = dict(carga.get("preferencias") or {})
        referencias = preferencias.pop("referencias_hijo", None)
        acudiente = _acudiente_de_un_hijo(usuario_id, preferencias, referencias)

        # La vista previa ya es la revision del kit: el admin la ajusto antes de
        # aprobar la lista. Promoverla conserva esos ajustes; sin ella (o si no
        # tiene nada comprable, o la lista cambio desde que se armo) se sigue
        # con el trabajo nuevo de siempre. Si el catalogo no responde al
        # comparar, se REINTENTA el evento: armar un trabajo nuevo ahora tiraria
        # los ajustes por un fallo pasajero.
        try:
            promovido = await trabajos.promover_vista_previa(
                self.motor_inteligencia,
                fila.agregado_id,
                colegio_id=str(colegio_id),
                grado=grado,
                anio_lectivo=anio,
                catalogo=self.catalogo,
                acudiente=acudiente,
            )
        except trabajos.RemotoCaido:
            return Resultado.REINTENTAR
        # Sin padre, o con el padre ya servido desde la vista previa, no queda
        # nada que armar. Con un padre de varios hijos en esta version el kit del
        # grado si sale de la vista previa, pero el suyo se arma como siempre:
        # no hay UN personaje que aplicarle sobre el kit del grado.
        if promovido is not None and (usuario_id is None or acudiente is not None):
            return Resultado.HECHO

        respuesta = await trabajos.crear(
            self.motor_inteligencia,
            hijos=[hijo],
            preferencias=preferencias,
            origen=origen,
            usuario_id=usuario_id,
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])

        # El trabajo ya es durable en `encolado`: `drenar` marcara el evento
        # publicado al devolver HECHO (dentro de la misma transaccion de la
        # pasada). Si el proceso muere durante el pipeline, el trabajo queda
        # reintentable (`POST /v1/trabajos/{id}/reintentar`) y el evento no se
        # reprocesa —no se arma un segundo kit para el mismo padre—.

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


def _acudiente_de_un_hijo(
    usuario_id: uuid.UUID | None, preferencias: dict[str, Any], referencias: Any
) -> dict[str, Any] | None:
    """El papa a quien armarle el kit desde la vista previa, o None.

    Solo si la version es de UN hijo: su personaje (`personaje_por_hijo` por su
    referencia) es el que se aplica sobre el kit del grado, como en la ruta
    rapida. Una version subida antes de que `subir_listas` guardara las
    referencias solo cuenta como de un hijo si no pidio personajes: sin saber
    de que hijo es, aplicar el de otro seria peor que armarle el kit de siempre.
    """
    if usuario_id is None:
        return None
    personajes = preferencias.get("personaje_por_hijo") or {}
    if isinstance(referencias, list):
        if len(referencias) != 1:
            return None
        elegidos = personajes.get(str(referencias[0])) or []
        personaje = str(elegidos[0]) if elegidos else None
    elif personajes:
        return None
    else:
        personaje = None
    return {"usuario_id": usuario_id, "preferencias": preferencias, "personaje": personaje}


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
