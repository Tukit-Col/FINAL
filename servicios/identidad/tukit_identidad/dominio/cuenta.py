from __future__ import annotations

import enum

CENTINELA_INVITADO = "sin-credencial"

CLAVE_MINIMA = 8


class Decision(enum.StrEnum):
    CREAR = "crear"
    PROMOVER = "promover"
    CONFLICTO = "conflicto"


class ClaveDebil(Exception):
    pass


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
