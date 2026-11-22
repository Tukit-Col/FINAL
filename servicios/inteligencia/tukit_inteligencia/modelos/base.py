"""Enumerados, pesos por omision y modelos base de Inteligencia.

Decisiones:
- `PESOS_POR_OMISION` son los puntajes medios de la pregunta P21 de la encuesta a acudientes
  (n = 60; 4 puntos al primer lugar, 1 al ultimo) divididos entre 10 para que sumen 1.
- El kit `A tu Medida` es la mejor marca que cabe en el tope del acudiente o, sin tope, en la mitad
  de camino entre Ahorrador y Premium; como el Fan, solo existe si el acudiente lo pidio.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Texto = JSON().with_variant(JSONB(), "postgresql")


class EstadoTrabajo(enum.StrEnum):

    ENCOLADO = "encolado"
    PROCESANDO = "procesando"
    ESPERA_REVISION = "espera_revision"
    PUBLICADO = "publicado"
    FALLIDO = "fallido"
    CANCELADO = "cancelado"


TRANSICIONES: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    EstadoTrabajo.ENCOLADO: frozenset(
        {EstadoTrabajo.PROCESANDO, EstadoTrabajo.FALLIDO, EstadoTrabajo.CANCELADO}
    ),
    EstadoTrabajo.PROCESANDO: frozenset(
        {EstadoTrabajo.ESPERA_REVISION, EstadoTrabajo.FALLIDO, EstadoTrabajo.PUBLICADO}
    ),
    EstadoTrabajo.ESPERA_REVISION: frozenset(
        {
            EstadoTrabajo.PUBLICADO,
            EstadoTrabajo.PROCESANDO,
            EstadoTrabajo.ENCOLADO,
            EstadoTrabajo.CANCELADO,
        }
    ),
    EstadoTrabajo.PUBLICADO: frozenset({EstadoTrabajo.CANCELADO}),
    EstadoTrabajo.FALLIDO: frozenset({EstadoTrabajo.ENCOLADO, EstadoTrabajo.CANCELADO}),
    EstadoTrabajo.CANCELADO: frozenset(),
}


class EstadoEtapa(enum.StrEnum):

    PENDIENTE = "pendiente"
    OK = "ok"
    DEGRADADA = "degradada"
    FALLIDA = "fallida"
    OMITIDA = "omitida"


class EstadoResolucion(enum.StrEnum):

    RESUELTO_AUTO = "RESUELTO_AUTO"
    AMBIGUO = "AMBIGUO"
    SIN_MATCH = "SIN_MATCH"
    HUECO_CATALOGO = "HUECO_CATALOGO"


class PerfilKit(enum.StrEnum):

    AHORRADOR = "Ahorrador"
    FAN = "Fan"
    A_TU_MEDIDA = "A tu Medida"
    PREMIUM = "Premium"


PESOS_POR_OMISION: dict[str, float] = {
    "precio": 0.285,
    "marca_exigida": 0.273,
    "calidad": 0.255,
    "personaje": 0.187,
}
