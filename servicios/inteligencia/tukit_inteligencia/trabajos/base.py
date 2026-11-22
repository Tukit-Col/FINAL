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
TAU_POR_OMISION = 0.75
ANIO_LECTIVO_POR_OMISION = 2026


def tau() -> float:
    try:
        return float(os.environ.get("TUKIT_TAU", TAU_POR_OMISION))
    except ValueError:
        return TAU_POR_OMISION


def autopublicar() -> bool:
    return os.environ.get("TUKIT_AUTOPUBLICAR", "").strip().lower() in {"1", "true", "si"}


def ahora() -> datetime:
    return datetime.now(UTC)


class SolicitudNoCancelable(Exception):
    def __init__(self, codigo: str, mensaje: str, estado: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado = estado


class CambioNoPermitido(Exception):
    def __init__(self, codigo: str, mensaje: str, estado: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado = estado


class CheckoutRechazado(Exception):
    def __init__(self, estado: int, cuerpo: dict[str, Any]) -> None:
        super().__init__(str(cuerpo.get("error") or estado))
        self.estado = estado
        self.cuerpo = cuerpo


class TrabajoProtegido(Exception):
    def __init__(self, estado: str) -> None:
        super().__init__(f"un trabajo en {estado} esta protegido contra borrado")
        self.estado = estado


class SinProductoQueValidar(Exception):
    def __init__(self, sku: str | None) -> None:
        super().__init__(sku or "sin_sku")
        self.sku = sku


class PreviewNoPublicable(Exception):
    pass


class NoCanonizable(Exception):
    pass


class KitsPublicadosNoEditables(Exception):
    pass


class BorradorDesactualizado(Exception):
    pass


ORIGEN_CANONICO = "canonico_lista"
ORIGENES_SIN_ACUDIENTE = frozenset({"preview_onboarding", ORIGEN_CANONICO})


async def _estado(conexion: Any, trabajo_id: uuid.UUID) -> str:
    return await RepoTrabajos(conexion).estado(trabajo_id)


async def _pasar_a(conexion: Any, trabajo_id: uuid.UUID, nuevo: str, **extra: Any) -> None:
    await RepoTrabajos(conexion).pasar_a(trabajo_id, nuevo, **extra)


async def _avisar_encolado(conexion: Any, trabajo_id: uuid.UUID) -> None:
    if url_broker():
        await RepoTrabajos(conexion).avisar_encolado(trabajo_id)


async def _publicar_evento(conexion: Any, trabajo_id: uuid.UUID) -> None:
    await RepoTrabajos(conexion).emitir_evento(trabajo_id)
