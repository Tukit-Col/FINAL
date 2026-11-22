"""Lectura de las preferencias del acudiente que el optimizador consulta (tope, pesos, Fan, A tu Medida)."""

from __future__ import annotations

from typing import Any

from .tipos import KitArmado


def _personajes_de(preferencias: dict[str, Any], hijo: str) -> tuple[str, ...]:
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    valores = por_hijo.get(hijo) or []
    return tuple(str(v) for v in valores)


def _tope(preferencias: dict[str, Any]) -> int | None:
    """El tope de gasto: el presupuesto tal cual, `None` si no hay.

    No se estira con `disposicion_sobreprecio`. Antes si (hasta un 10 %), y un
    acudiente que escribia "maximo $350.000" podia recibir un kit de $385.000:
    el sobreprecio dice cuanto mas pagaria por marca SIN tope, no cuanto se
    puede pasar del tope que el mismo puso (§3: restriccion DURA).
    """
    presupuesto = preferencias.get("presupuesto_por_hijo")
    if not isinstance(presupuesto, int) or presupuesto <= 0:
        return None
    return presupuesto


def _pesos(valor: int) -> str:
    """Pesos como los lee un papa colombiano: `$443.255`, no `$443,255`."""
    return "$" + f"{valor:,}".replace(",", ".")


def quiere_fan(preferencias: dict[str, Any]) -> bool:
    """El kit Fan solo existe si el acudiente pidio un personaje (ADR 0030)."""
    return any(preferencias.get("personaje_por_hijo") or {})


def quiere_a_tu_medida(preferencias: dict[str, Any]) -> bool:
    """`A tu Medida` solo existe si eligio el punto medio o declaro un tope."""
    return preferencias.get("prioridad") == "equilibrio" or _tope(preferencias) is not None


def _tope_de_a_tu_medida(
    preferencias: dict[str, Any], ahorrador: KitArmado, premium: KitArmado
) -> tuple[int, bool]:
    """El tope contra el que se arma `A tu Medida`, y si lo puso el acudiente.

    Sin tope declarado se usa la mitad de camino entre el Ahorrador y el
    Premium: subir de marca donde vale la pena sin llegar a pagar el Premium.
    Es el mismo criterio con el que el benchmark Laya vs NSGA-II fijo el
    presupuesto de su escenario intermedio.
    """
    tope = _tope(preferencias)
    if tope is not None:
        return tope, True
    return (ahorrador.total_cop + premium.total_cop) // 2, False
