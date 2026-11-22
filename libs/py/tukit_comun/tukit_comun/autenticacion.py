"""Lectura del encabezado `Authorization`, igual para todos los servicios."""

from __future__ import annotations


def token_bearer(authorization: str | None) -> str | None:
    """El token del encabezado `Authorization`: `Bearer <token>` o el token pelado."""
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


__all__ = ["token_bearer"]
