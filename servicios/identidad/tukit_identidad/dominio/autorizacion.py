from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..modelos import AmbitoTipo


@dataclass(frozen=True, slots=True)
class Ambito:
    tipo: AmbitoTipo
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (self.tipo is AmbitoTipo.GLOBAL) != (self.id is None):
            raise ValueError(
                f"Ambito incoherente: tipo={self.tipo} con id={self.id}. "
                "El ambito global no lleva identificador, y los demas si."
            )

    @classmethod
    def global_(cls) -> Ambito:
        return cls(AmbitoTipo.GLOBAL)

    @classmethod
    def colegio(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.COLEGIO, id)

    @classmethod
    def sede(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.SEDE, id)

    @classmethod
    def matricula(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.MATRICULA, id)
