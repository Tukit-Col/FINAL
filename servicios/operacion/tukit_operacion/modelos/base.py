from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Texto = JSON().with_variant(JSONB(), "postgresql")


class OrigenCaso(enum.StrEnum):
    ACUDIENTE = "acudiente"
    COLEGIO = "colegio"
    OPERADOR = "operador"
    SISTEMA = "sistema"


class CategoriaCaso(enum.StrEnum):
    PAGO = "pago"
    STOCK = "stock"
    ENTREGA = "entrega"
    MAPEO_LISTA = "mapeo_lista"
    AUTENTICACION = "autenticacion"
    PETICION = "peticion"
    QUEJA = "queja"
    RECLAMO = "reclamo"
    SUGERENCIA = "sugerencia"


CATEGORIAS_CASO_ACUDIENTE: frozenset[CategoriaCaso] = frozenset(
    {
        CategoriaCaso.PETICION,
        CategoriaCaso.QUEJA,
        CategoriaCaso.RECLAMO,
        CategoriaCaso.SUGERENCIA,
        CategoriaCaso.PAGO,
        CategoriaCaso.ENTREGA,
    }
)


class EstadoCaso(enum.StrEnum):
    ABIERTO = "abierto"
    EN_GESTION = "en_gestion"
    ESPERANDO_TERCERO = "esperando_tercero"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"

    @classmethod
    def inactivos(cls) -> frozenset[EstadoCaso]:
        return frozenset({cls.RESUELTO, cls.CERRADO})


class Prioridad(enum.StrEnum):
    URGENTE = "urgente"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


ORDEN_PRIORIDAD: dict[Prioridad, int] = {
    Prioridad.URGENTE: 0,
    Prioridad.ALTA: 1,
    Prioridad.MEDIA: 2,
    Prioridad.BAJA: 3,
}


SLA_HORAS: dict[CategoriaCaso, int | None] = {
    CategoriaCaso.PETICION: 15 * 24,
    CategoriaCaso.QUEJA: 15 * 24,
    CategoriaCaso.RECLAMO: 15 * 24,
    CategoriaCaso.SUGERENCIA: 30 * 24,
    CategoriaCaso.PAGO: 24,
    CategoriaCaso.ENTREGA: 48,
    CategoriaCaso.STOCK: 48,
    CategoriaCaso.MAPEO_LISTA: 24,
    CategoriaCaso.AUTENTICACION: 4,
}


PRIORIDAD_POR_CATEGORIA: dict[CategoriaCaso, Prioridad] = {
    CategoriaCaso.PAGO: Prioridad.URGENTE,
    CategoriaCaso.AUTENTICACION: Prioridad.URGENTE,
    CategoriaCaso.ENTREGA: Prioridad.ALTA,
    CategoriaCaso.STOCK: Prioridad.ALTA,
    CategoriaCaso.MAPEO_LISTA: Prioridad.ALTA,
    CategoriaCaso.RECLAMO: Prioridad.ALTA,
    CategoriaCaso.QUEJA: Prioridad.MEDIA,
    CategoriaCaso.PETICION: Prioridad.MEDIA,
    CategoriaCaso.SUGERENCIA: Prioridad.BAJA,
}
