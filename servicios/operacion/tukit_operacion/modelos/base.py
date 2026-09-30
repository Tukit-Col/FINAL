"""Base declarativa y vocabulario del servicio de Operacion.

Los enums son los del contrato de lectura (`libs/ts/tukit-contrato/src/
operacion.ts`), no una traduccion suya. `operacion` es el servicio de casos,
PQRS, notificaciones, auditoria y telemetria: cada falla del flujo
transaccional (la saga de pago) abre un Caso aqui, y las PQRS que abre una
persona tambien.

El SLA por categoria (`SLA_HORAS`) vive como dato porque es la promesa que la
UI muestra por escrito: un derecho de peticion tiene un termino legal (Ley
1755) y una falla de pago un reloj de negocio. Colapsarlos en un valor unico
esconderia la diferencia que hace util el `vence_en`.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Texto = JSON().with_variant(JSONB(), "postgresql")


class OrigenCaso(enum.StrEnum):
    """De donde nacio el caso. `sistema` son las fallas de la saga; el resto
    son PQRS que abre una persona."""

    ACUDIENTE = "acudiente"
    COLEGIO = "colegio"
    OPERADOR = "operador"
    SISTEMA = "sistema"


class CategoriaCaso(enum.StrEnum):
    """Las cinco fallas nombradas de la saga + las categorias de PQRS.

    `mapeo_lista` y `autenticacion` las abre el SISTEMA, no una persona: no
    tienen sentido en un formulario de ayuda y por eso no estan en
    `CATEGORIAS_CASO_ACUDIENTE`.
    """

    PAGO = "pago"
    STOCK = "stock"
    ENTREGA = "entrega"
    MAPEO_LISTA = "mapeo_lista"
    AUTENTICACION = "autenticacion"
    PETICION = "peticion"
    QUEJA = "queja"
    RECLAMO = "reclamo"
    SUGERENCIA = "sugerencia"


# El subconjunto que un acudiente puede elegir al abrir un caso desde el centro
# de ayuda. Un intento de abrir una categoria de saga se rechaza con 422: esas
# las abre el sistema. Coincide con `CATEGORIAS_CASO_ACUDIENTE` del contrato TS.
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
    """Los cinco estados de un caso. `resuelto` y `cerrado` son inactivos."""

    ABIERTO = "abierto"
    EN_GESTION = "en_gestion"
    ESPERANDO_TERCERO = "esperando_tercero"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"

    @classmethod
    def inactivos(cls) -> frozenset[EstadoCaso]:
        return frozenset({cls.RESUELTO, cls.CERRADO})


class Prioridad(enum.StrEnum):
    """Ordena la bandeja. El operador entra por lo urgente primero."""

    URGENTE = "urgente"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


# El orden con el que la bandeja se ordena: urgente arriba. Espeja
# `ORDEN_PRIORIDAD` del contrato TS.
ORDEN_PRIORIDAD: dict[Prioridad, int] = {
    Prioridad.URGENTE: 0,
    Prioridad.ALTA: 1,
    Prioridad.MEDIA: 2,
    Prioridad.BAJA: 3,
}


# El termino, en horas, para responder cada categoria. Los de PQRS salen de la
# Ley 1755: peticion 15 dias habiles, queja/reclamo 15, sugerencia sin termino
# estricto (se toma 30 dias como guia interna). Se aproximan a horas de
# calendario para el `vence_en` que la UI pinta; el termino legal fino se
# recalcula en la gestion. Pago y entrega son relojes de negocio, no legales.
SLA_HORAS: dict[CategoriaCaso, int | None] = {
    CategoriaCaso.PETICION: 15 * 24,
    CategoriaCaso.QUEJA: 15 * 24,
    CategoriaCaso.RECLAMO: 15 * 24,
    CategoriaCaso.SUGERENCIA: 30 * 24,
    CategoriaCaso.PAGO: 24,
    CategoriaCaso.ENTREGA: 48,
    # Categorias de sistema: no las abre una persona, no tienen termino de PQRS.
    CategoriaCaso.STOCK: 48,
    CategoriaCaso.MAPEO_LISTA: 24,
    CategoriaCaso.AUTENTICACION: 4,
}


# La prioridad con la que nace un caso segun su categoria. Una falla de pago
# bloquea plata (urgente); una sugerencia puede esperar (baja).
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
