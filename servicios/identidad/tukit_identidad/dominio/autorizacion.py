"""El ambito sobre el que se pregunta un permiso, como dato puro.

`Ambito` reemplaza comparar `if usuario.rol not in roles`: la pregunta
correcta es "que puede hacer este usuario SOBRE ESTE recurso", y `Ambito` es
justo ese recurso, tipado. Las funciones que RESUELVEN la pregunta contra la
base (`puede`, `roles_vigentes`, `campos_visibles`, `matriculas_visibles`,
`_cadena_de_contencion`) no son dominio puro —hacen SQL— y viven en
`repositorios/identidad.py`. Ver ADR 0013.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..modelos import AmbitoTipo


@dataclass(frozen=True, slots=True)
class Ambito:
    """Sobre que se pregunta. `GLOBAL` no lleva identificador."""

    tipo: AmbitoTipo
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        # Misma regla que el CHECK `asignacion_ambito_coherente`. Se valida
        # tambien aqui para que un ambito mal armado falle al construirse y no
        # al comparar, donde el error seria un permiso denegado sin explicacion.
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
