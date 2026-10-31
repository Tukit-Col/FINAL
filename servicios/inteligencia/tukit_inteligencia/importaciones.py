"""Las listas que sube un acudiente, de inteligencia al catalogo (ADR 0040).

`POST /v1/listas/subir` percibe el PDF de cada hijo y lo importa al catalogo.
Antes las dos cosas vivian solo dentro de la peticion: con el catalogo caido
salia un 500 y lo ya percibido se perdia (H-B-01). La peticion sigue intentando
cada destino; lo que no entra porque el catalogo no responde queda aqui:

- `guardar` lo deja `pendiente` en `importacion_lista`, con todo lo que el
  catalogo necesita, en una sola transaccion. La percepcion, que es la etapa
  cara, no se repite;
- `reintentar_pendientes` lo importa desde el bucle del trabajador.

Con el catalogo arriba no se guarda nada: la copia de la lista, que puede traer
lo que el modelo transcribio de la pagina, y la del PDF son las del catalogo.
Inteligencia solo tiene la suya mientras la necesita.

Cada destino viaja con su `clave_idempotencia`: dos intentos de la misma fila,
o un reintento despues de una respuesta que se perdio, dan una sola version en
el catalogo.

Que es una caida lo decide `RemotoCaido.transitorio`. Sin respuesta, 5xx, 408 o
429 se reintentan con espera exponencial; un rechazo (otro 4xx) deja la fila
`fallida` con su diagnostico, porque reintentarlo daria lo mismo.
"""

from __future__ import annotations

import base64
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert, null, select, update
from tukit_comun import derivar

from .modelos import ImportacionLista
from .remoto import RemotoCaido

IMPORTACION = ImportacionLista.__table__

PENDIENTE = "pendiente"
IMPORTADA = "importada"
FALLIDA = "fallida"

# Lo que una fila queda reservada mientras una vuelta del trabajador la
# intenta. Cubre de sobra la espera del cliente del catalogo
# (`ESPERA_SEGUNDOS`, 60 s), para que otra vuelta no la tome a la vez. Si
# igual coinciden, la clave hace que el catalogo cree una sola version.
_EN_VUELO = timedelta(minutes=2)
# La espera despues de cada caida: 5 s la primera, el doble cada vez y como
# mucho 5 minutos.
_ESPERA_INICIAL = 5.0
_ESPERA_TOPE = 300.0

log = logging.getLogger(__name__)


def _ahora() -> datetime:
    return datetime.now(UTC)


def clave_de(subida_id: uuid.UUID, destino: Destino) -> uuid.UUID:
    """La clave de idempotencia de un destino de una subida.

    Es por subida y no por contenido: un acudiente que vuelve a subir la misma
    lista hace una version nueva, igual que antes.
    """
    return derivar(
        "importacion_lista", str(subida_id), destino.colegio_id, destino.grado, str(destino.anio_lectivo)
    )


@dataclass
class Destino:
    """Un (colegio, grado, anio) de una subida, con lo percibido para importarlo."""

    colegio_id: str
    grado: str
    anio_lectivo: int
    referencias: list[str]
    items: list[dict[str, Any]]
    percepcion_cruda: list[dict[str, Any]]
    documento: bytes
    colegio_datos: dict[str, Any] | None = None


@dataclass(frozen=True)
class Intento:
    """Como quedo una fila despues de intentarla."""

    estado: str
    version_id: str | None = None
    error: RemotoCaido | None = None


async def guardar(
    motor: Any,
    subida_id: uuid.UUID,
    destinos: Sequence[Destino],
    *,
    caida: RemotoCaido,
    contacto_referencia: str | None,
    preferencias: dict[str, Any] | None,
    origen: str = "sugerencia_padre",
) -> list[uuid.UUID]:
    """Deja `pendiente` lo que el catalogo no recibio en la peticion, todo o nada.

    El primer destino es el que el catalogo no recibio (`caida`): cuenta como
    un intento, y su espera corre desde ya. Los demas no se intentaron y el
    trabajador puede tomarlos en su siguiente vuelta. Devuelve los ids, en orden.
    """
    log.warning(
        "subida %s: el catalogo no respondio (%s); %d destinos quedan pendientes",
        subida_id,
        caida,
        len(destinos),
    )
    ahora = _ahora()
    filas = [
        {
            "id": uuid.uuid4(),
            "subida_id": subida_id,
            "clave_idempotencia": clave_de(subida_id, d),
            "referencias": d.referencias,
            "contacto_referencia": contacto_referencia,
            "colegio_id": d.colegio_id,
            "grado": d.grado,
            "anio_lectivo": d.anio_lectivo,
            "carga": {
                "items": d.items,
                "percepcion_cruda": d.percepcion_cruda,
                "preferencias": preferencias,
                "colegio_datos": d.colegio_datos,
                "origen": origen,
            },
            "documento": d.documento,
            "estado": PENDIENTE,
            "intentos": 1 if posicion == 0 else 0,
            "error": caida.detalle if posicion == 0 else None,
            "proximo_intento_en": ahora + _espera(1) if posicion == 0 else ahora,
        }
        for posicion, d in enumerate(destinos)
    ]
    async with motor.engine.begin() as conexion:
        await conexion.execute(insert(IMPORTACION), filas)
    return [f["id"] for f in filas]


async def reintentar_pendientes(
    motor: Any, *, catalogo: Any, limite: int = 10, ahora: datetime | None = None
) -> int:
    """Una vuelta del reintento: importa hasta `limite` filas vencidas.

    Toma una fila por vez con `FOR UPDATE SKIP LOCKED` y la reserva en la misma
    transaccion corta, asi que dos trabajadores no toman la misma. La llamada al
    catalogo va fuera de la transaccion. Si el catalogo sigue caido, la vuelta
    corta ahi: insistir con las demas solo sumaria esperas. Devuelve cuantas
    importo. `ahora` existe para las pruebas.
    """
    momento = ahora or _ahora()
    importadas = 0
    for _ in range(limite):
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(IMPORTACION)
                    .where(IMPORTACION.c.estado == PENDIENTE, IMPORTACION.c.proximo_intento_en <= momento)
                    .order_by(IMPORTACION.c.proximo_intento_en)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).first()
            if fila is None:
                break
            await conexion.execute(
                update(IMPORTACION)
                .where(IMPORTACION.c.id == fila.id)
                .values(proximo_intento_en=momento + _EN_VUELO)
            )
        intento = await _intentar(motor, fila, catalogo=catalogo, ahora=ahora)
        if intento.estado == IMPORTADA:
            importadas += 1
        elif intento.estado == PENDIENTE:
            break
    return importadas


def _espera(intentos: int) -> timedelta:
    """5 s despues del primer intento fallido, el doble cada vez, con tope."""
    segundos = _ESPERA_INICIAL * 2 ** min(intentos - 1, 16)
    return timedelta(seconds=min(segundos, _ESPERA_TOPE))


async def _intentar(motor: Any, fila: Any, *, catalogo: Any, ahora: datetime | None = None) -> Intento:
    """Una importacion de una fila, y lo que deja escrito.

    La espera del siguiente intento se cuenta desde que termino este, no desde
    que empezo: si no, un intento que se comio los 60 s del cliente dejaria la
    fila vencida de nuevo al instante.
    """
    carga = fila.carga
    intentos = fila.intentos + 1
    try:
        respuesta = await catalogo.importar_lista(
            colegio_id=fila.colegio_id,
            grado=fila.grado,
            anio_lectivo=fila.anio_lectivo,
            items=carga["items"],
            documento_base64=base64.b64encode(fila.documento).decode(),
            percepcion_cruda=carga["percepcion_cruda"],
            contacto_referencia=fila.contacto_referencia,
            preferencias=carga.get("preferencias"),
            colegio_datos=carga.get("colegio_datos"),
            origen=carga.get("origen", "sugerencia_padre"),
            clave_idempotencia=str(fila.clave_idempotencia),
        )
    except RemotoCaido as error:
        if not error.transitorio:
            log.error(
                "importacion %s rechazada por el catalogo en el intento %d: %s", fila.id, intentos, error
            )
            await _actualizar(motor, [fila.id], estado=FALLIDA, intentos=intentos, error=error.detalle)
            return Intento(FALLIDA, error=error)
        espera = _espera(intentos)
        log.warning(
            "importacion %s sigue pendiente tras el intento %d (%s); se reintenta en %d s",
            fila.id,
            intentos,
            error,
            espera.total_seconds(),
        )
        fin = ahora or _ahora()
        await _actualizar(
            motor, [fila.id], intentos=intentos, error=error.detalle, proximo_intento_en=fin + espera
        )
        return Intento(PENDIENTE, error=error)

    version_id = str(respuesta["version_id"])
    # Ya esta en el catalogo: desde aqui la copia buena del PDF y de lo
    # percibido es la suya, y esta se vacia.
    await _actualizar(
        motor,
        [fila.id],
        estado=IMPORTADA,
        intentos=intentos,
        version_id=version_id,
        error=None,
        carga=null(),
        documento=None,
    )
    return Intento(IMPORTADA, version_id=version_id)


async def _actualizar(motor: Any, ids: Sequence[uuid.UUID], **valores: Any) -> None:
    """Escribe sobre filas que siguen `pendiente`; una importada no se toca.

    Si dos vueltas del trabajador llegaran a intentar la misma fila, la que
    termina segunda no devuelve a `pendiente` la que la otra ya importo.
    """
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(IMPORTACION)
            .where(IMPORTACION.c.id.in_(list(ids)), IMPORTACION.c.estado == PENDIENTE)
            .values(**valores)
        )


__all__ = [
    "FALLIDA",
    "IMPORTACION",
    "IMPORTADA",
    "PENDIENTE",
    "Destino",
    "Intento",
    "clave_de",
    "guardar",
    "reintentar_pendientes",
]
