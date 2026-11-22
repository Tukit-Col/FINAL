from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Clasificacion(enum.StrEnum):
    PUBLICO = "publico"
    INTERNO = "interno"
    PERSONAL = "personal"
    PERSONAL_SENSIBLE = "personal_sensible"
    MENOR = "menor"


ORDEN_CLASIFICACION: dict[Clasificacion, int] = {
    Clasificacion.PUBLICO: 0,
    Clasificacion.INTERNO: 1,
    Clasificacion.PERSONAL: 2,
    Clasificacion.PERSONAL_SENSIBLE: 3,
    Clasificacion.MENOR: 4,
}


class AmbitoTipo(enum.StrEnum):
    GLOBAL = "global"
    COLEGIO = "colegio"
    SEDE = "sede"
    MATRICULA = "matricula"


class EstadoMatricula(enum.StrEnum):
    ACTIVA = "activa"
    RETIRADA = "retirada"
    GRADUADA = "graduada"
    ARCHIVADA = "archivada"

    @classmethod
    def cerrados(cls) -> frozenset[EstadoMatricula]:
        return frozenset({cls.RETIRADA, cls.GRADUADA, cls.ARCHIVADA})
