from __future__ import annotations

import uuid
from dataclasses import dataclass

GRADOS = (
    "Parvulos",
    "Prejardin",
    "Jardin",
    "Transicion",
    "Primero",
    "Segundo",
    "Tercero",
    "Cuarto",
    "Quinto",
    "Sexto",
    "Septimo",
    "Octavo",
    "Noveno",
    "Decimo",
    "Once",
)


@dataclass
class HijoMatricula:
    colegio_id: uuid.UUID
    grado: str
    apodo: str | None = None
