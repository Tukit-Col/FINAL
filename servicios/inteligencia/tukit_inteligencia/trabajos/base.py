"""Tablas, configuracion, constantes y excepciones del recurso `trabajo`."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from tukit_comun.broker import url_broker

from ..modelos import (
    Base,
)
from ..repositorios.trabajos import RepoTrabajos

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


async def _estado(conexion: Any, trabajo_id: uuid.UUID) -> str:
    return await RepoTrabajos(conexion).estado(trabajo_id)


async def _pasar_a(conexion: Any, trabajo_id: uuid.UUID, nuevo: str, **extra: Any) -> None:
    await RepoTrabajos(conexion).pasar_a(trabajo_id, nuevo, **extra)


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
