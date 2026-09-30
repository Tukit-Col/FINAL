"""Los grados escolares y la forma plana de un hijo a matricular. Puro: sin SQL,
sin HTTP (ADR 0019).

Vive aparte para que el router —que recibe el cuerpo del formulario— y el poller
—que arma un hijo sintetico cuando un colegio se vuelve aliado— compartan la
misma lista canonica de grados y la misma forma sin acoplarse entre si. El SQL
que materializa cada hijo (estudiante + matricula + vinculo, todo derivado) vive
en `repositorios/identidad.py`; aqui solo el dato.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

# Los quince grados del corpus, en orden escolar. Va como constante y no como
# consulta porque no es un dato del sistema sino del sistema educativo
# colombiano: derivarlo de las listas cargadas haria que un colegio sin lista
# publicada desapareciera del desplegable.
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
    """Un hijo tal como se manda a materializar: colegio y grado bastan para
    armar el kit. El `apodo` es opcional y es lo unico que identifica al menor;
    se guarda cifrado. NUNCA el nombre legal (minimizacion, Ley 1581 Art. 4)."""

    colegio_id: uuid.UUID
    grado: str
    apodo: str | None = None
