"""Base declarativa y vocabulario compartido del servicio de Identidad."""

from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Clasificacion(enum.StrEnum):
    """Sensibilidad del dato, en los cinco niveles del proyecto.

    Mide QUE TAN sensible es el dato. No dice quien puede verlo: eso lo expresa
    el permiso, y son dos ejes distintos. Lo unico que la clasificacion deriva
    es el valor por omision: todo campo `MENOR` o `PERSONAL_SENSIBLE` nace
    denegado y todo campo `PUBLICO` nace permitido.

    Confundir los dos ejes lleva a implementar la mitad del mecanismo creyendo
    que esta completo, que es lo que el Anexo M senalo del rediseno.
    """

    PUBLICO = "publico"
    INTERNO = "interno"
    PERSONAL = "personal"
    PERSONAL_SENSIBLE = "personal_sensible"
    MENOR = "menor"


# Orden de menor a mayor sensibilidad. Sirve para comparar un permiso contra la
# clasificacion del campo que quiere alcanzar.
ORDEN_CLASIFICACION: dict[Clasificacion, int] = {
    Clasificacion.PUBLICO: 0,
    Clasificacion.INTERNO: 1,
    Clasificacion.PERSONAL: 2,
    Clasificacion.PERSONAL_SENSIBLE: 3,
    Clasificacion.MENOR: 4,
}


class AmbitoTipo(enum.StrEnum):
    """Alcance sobre el que rige una asignacion de rol.

    La jerarquia es `global > colegio > sede > matricula`. Un rol otorgado
    sobre un colegio alcanza sus sedes y las matriculas de esas sedes; al
    reves no.
    """

    GLOBAL = "global"
    COLEGIO = "colegio"
    SEDE = "sede"
    MATRICULA = "matricula"


class EstadoMatricula(enum.StrEnum):
    """Estados de la relacion de un estudiante con una sede.

    El diccionario de datos registra una discrepancia entre documentos: el
    Anexo M habla de un estado `historica` que no existe en el CHECK del
    esquema objetivo. Se adopta el vocabulario del esquema, que es el que
    viene con DDL, y la politica de retencion se escribe contra el conjunto
    `{RETIRADA, GRADUADA, ARCHIVADA}` y no contra un valor inexistente.
    """

    ACTIVA = "activa"
    RETIRADA = "retirada"
    GRADUADA = "graduada"
    ARCHIVADA = "archivada"

    @classmethod
    def cerrados(cls) -> frozenset[EstadoMatricula]:
        return frozenset({cls.RETIRADA, cls.GRADUADA, cls.ARCHIVADA})
