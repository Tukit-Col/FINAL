"""Las listas que sube un acudiente, de Inteligencia al Catalogo.

Decisiones:
- Lo que no entra porque el Catalogo no responde queda `pendiente` en `importacion_lista`, con todo
  lo que el Catalogo necesita, en una sola transaccion; la percepcion, que es la etapa cara, no se
  repite. `reintentar_pendientes` lo importa desde el bucle del trabajador.
- Con el Catalogo arriba no se guarda nada: la copia de la lista y la del PDF son las del Catalogo.
- Cada destino viaja con su `clave_idempotencia`, asi que dos intentos o un reintento tras una
  respuesta perdida dan una sola version.
- `RemotoCaido.transitorio` decide que es una caida: sin respuesta, 5xx, 408 o 429 se reintentan
  con espera exponencial; otro 4xx es un rechazo.
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

_EN_VUELO = timedelta(minutes=2)
_ESPERA_INICIAL = 5.0
_ESPERA_TOPE = 300.0

log = logging.getLogger(__name__)


def _ahora() -> datetime:
    return datetime.now(UTC)


def clave_de(subida_id: uuid.UUID, destino: Destino) -> uuid.UUID:
    return derivar(
        "importacion_lista", str(subida_id), destino.colegio_id, destino.grado, str(destino.anio_lectivo)
    )


@dataclass
class Destino:

    colegio_id: str
    grado: str
    anio_lectivo: int
    referencias: list[str]
    items: list[dict[str, Any]]
    percepcion_cruda: list[dict[str, Any]]
    documento: bytes
    colegio_datos: dict[str, Any] | None = None
    apodos: dict[str, str] | None = None


@dataclass(frozen=True)
class Intento:

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
                **({"apodos_cifrados": _cifrar_apodos(d.apodos)} if d.apodos else {}),
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
    segundos = _ESPERA_INICIAL * 2 ** min(intentos - 1, 16)
    return timedelta(seconds=min(segundos, _ESPERA_TOPE))


async def _intentar(motor: Any, fila: Any, *, catalogo: Any, ahora: datetime | None = None) -> Intento:
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
            referencias=list(fila.referencias or ()),
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
    apodos = _descifrar_apodos(carga.get("apodos_cifrados"))
    if apodos:
        from . import apodos_subida

        await apodos_subida.guardar(motor, version_id, fila.contacto_referencia, apodos)
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


def _cifrar_apodos(apodos: dict[str, str]) -> str:
    import json

    from tukit_comun.cifrado import cifrador_desde_entorno

    return base64.b64encode(cifrador_desde_entorno().cifrar(json.dumps(apodos).encode("utf-8"))).decode()


def _descifrar_apodos(texto: Any) -> dict[str, str]:
    if not texto:
        return {}
    import json

    from tukit_comun.cifrado import cifrador_desde_entorno

    try:
        crudo = cifrador_desde_entorno().descifrar(base64.b64decode(str(texto)))
        datos = json.loads(crudo.decode("utf-8"))
    except Exception:
        log.warning("apodos ilegibles en una importacion pendiente; se importa sin ellos")
        return {}
    return {str(k): str(v) for k, v in datos.items() if v} if isinstance(datos, dict) else {}


async def _actualizar(motor: Any, ids: Sequence[uuid.UUID], **valores: Any) -> None:
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
