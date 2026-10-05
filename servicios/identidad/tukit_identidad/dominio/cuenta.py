"""La decision de que hacer con un correo entrante, sin tocar la base.

Tres caminos y nada mas: un correo libre se CREA, un invitado (el centinela
`sin-credencial` que dejo `registrar_contacto` cuando el pipeline solo
necesitaba un id) se PROMUEVE a cuenta real, y un correo que ya tiene
credencial de verdad es CONFLICTO. El SQL que resuelve cual es cual vive en el
repo; aqui solo la regla, para poder probarla sin fixtures (ADR 0019).
"""

from __future__ import annotations

import enum

# El mismo centinela que `RepoIdentidad.registrar_contacto` escribe para un
# contacto sin clave utilizable. No es un hash: ningun verificador lo acepta.
CENTINELA_INVITADO = "sin-credencial"

# Largo minimo de clave. No se exige composicion (mayusculas/simbolos): la
# evidencia de usabilidad dice que empuja a la gente a patrones peores y a
# reusar. Largo es la palanca que si sube el costo de adivinar.
CLAVE_MINIMA = 8


class Decision(enum.StrEnum):
    CREAR = "crear"
    PROMOVER = "promover"
    CONFLICTO = "conflicto"


class ClaveDebil(Exception):
    """La clave no llega al largo minimo. El router lo traduce a 422."""


def es_invitado(clave_hash: str | None) -> bool:
    return clave_hash == CENTINELA_INVITADO


def decide_creacion(clave_hash_actual: str | None) -> Decision:
    if clave_hash_actual is None:
        return Decision.CREAR
    if es_invitado(clave_hash_actual):
        return Decision.PROMOVER
    return Decision.CONFLICTO


def validar_clave(clave: str) -> None:
    if len(clave) < CLAVE_MINIMA:
        raise ClaveDebil()
