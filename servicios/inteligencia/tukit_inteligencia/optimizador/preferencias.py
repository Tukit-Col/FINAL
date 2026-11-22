from __future__ import annotations

from typing import Any

from .tipos import KitArmado


def _personajes_de(preferencias: dict[str, Any], hijo: str) -> tuple[str, ...]:
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    valores = por_hijo.get(hijo) or []
    return tuple(str(v) for v in valores)


def _tope(preferencias: dict[str, Any]) -> int | None:
    presupuesto = preferencias.get("presupuesto_por_hijo")
    if not isinstance(presupuesto, int) or presupuesto <= 0:
        return None
    return presupuesto


def _pesos(valor: int) -> str:
    return "$" + f"{valor:,}".replace(",", ".")


def quiere_fan(preferencias: dict[str, Any]) -> bool:
    return any(preferencias.get("personaje_por_hijo") or {})


def quiere_a_tu_medida(preferencias: dict[str, Any]) -> bool:
    return preferencias.get("prioridad") == "equilibrio" or _tope(preferencias) is not None


def _tope_de_a_tu_medida(
    preferencias: dict[str, Any], ahorrador: KitArmado, premium: KitArmado
) -> tuple[int, bool]:
    tope = _tope(preferencias)
    if tope is not None:
        return tope, True
    return (ahorrador.total_cop + premium.total_cop) // 2, False
