"""El punto de entrada de la etapa: `armar_los_tres` y el kit `A tu Medida`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..modelos import PerfilKit
from .candidatos import aplicar_filtros_duros
from .frente import _proyectar, _surtibles, optimizar_frente
from .lineas import armar_kit
from .preferencias import _tope_de_a_tu_medida, quiere_a_tu_medida, quiere_fan
from .recomendacion import _mismos_productos, recomendar
from .tipos import Candidato, KitArmado, Renglon, SolucionFrente


def armar_los_tres(
    renglones: list[Renglon], preferencias: dict[str, Any] | None = None, *, semilla: int = 0
) -> list[KitArmado]:
    """Los kits del acudiente, con uno marcado. El punto de entrada de la etapa.

    Siempre `Ahorrador` y `Premium`. `Fan` solo si pidio un personaje y `A tu
    Medida` solo si eligio el punto medio o declaro un tope (ADR 0030): un kit
    que nadie pidio es ruido en la pantalla y trabajo para el revisor. Por eso
    los canonicos de una lista (sin preferencias) son solo dos.

    Calcula UN frente de Pareto y proyecta cada perfil sobre el —los kits son
    puntos del mismo frente, comparables entre si—. Si el frente esta vacio
    (nada que optimizar) cae a la heuristica, que da el mismo kit. La `semilla`
    hace el NSGA-II reproducible. (El nombre se conserva por sus llamadores.)
    """
    preferencias = preferencias or {}
    # Los filtros duros se aplican a los candidatos antes de todo lo demas, para
    # que ni el frente ni la heuristica de una sola opcion vean lo prohibido.
    renglones = aplicar_filtros_duros(renglones, preferencias)
    frente = optimizar_frente(renglones, preferencias, semilla=semilla)

    # Mapa sku -> Candidato por linea, para reconstruir la eleccion del frente.
    por_linea: dict[tuple[str, int], dict[str, Candidato]] = {}
    for renglon in renglones:
        if not renglon.informativa:
            por_linea[(renglon.hijo, renglon.orden)] = {c.sku: c for c in renglon.candidatos}

    def elecciones_de(punto: SolucionFrente | None) -> dict[tuple[str, int], Candidato] | None:
        if punto is None:
            return None
        return {
            clave: por_linea[clave][sku]
            for clave, sku in punto.asignacion.items()
            if clave in por_linea and sku in por_linea[clave]
        }

    def proyectado(perfil: PerfilKit) -> KitArmado:
        punto = _proyectar(frente, perfil.value) if frente else None
        return armar_kit(renglones, perfil.value, preferencias, elecciones=elecciones_de(punto))

    ahorrador = proyectado(PerfilKit.AHORRADOR)
    premium = proyectado(PerfilKit.PREMIUM)
    kits = [ahorrador]
    if quiere_fan(preferencias):
        kits.append(proyectado(PerfilKit.FAN))
    if quiere_a_tu_medida(preferencias):
        a_tu_medida = _armar_a_tu_medida(frente, renglones, preferencias, ahorrador, premium, elecciones_de)
        if a_tu_medida is not None:
            kits.append(a_tu_medida)
    kits.append(premium)
    return recomendar(kits, preferencias)


def _armar_a_tu_medida(
    frente: list[SolucionFrente],
    renglones: list[Renglon],
    preferencias: dict[str, Any],
    ahorrador: KitArmado,
    premium: KitArmado,
    elecciones_de: Callable[[SolucionFrente | None], dict[tuple[str, int], Candidato] | None],
) -> KitArmado | None:
    """La mejor marca del frente que cabe en el tope (o en la mitad de camino).

    Es el punto de mayor fidelidad con costo dentro del tope (desempata el menor
    costo). El benchmark Laya vs NSGA-II midio por que sale del frente y no de
    los kits fijos: caer al mas barato lograba el 40 % de la calidad posible y el
    frente traia un kit que cabia y lograba el 94 % (ADR 0029).

    Devuelve `None` cuando no habria un kit distinto que mostrar: nada que
    optimizar, ningun punto cabe, o el punto es el mismo Ahorrador o el mismo
    Premium. Mostrar dos veces el mismo kit con otro nombre confunde.
    """
    if not frente:
        return None
    tope, _ = _tope_de_a_tu_medida(preferencias, ahorrador, premium)
    caben = [s for s in _surtibles(frente) if s.costo <= tope]
    if not caben:
        return None
    punto = max(caben, key=lambda s: (s.fidelidad, -s.costo, s.disponibilidad))
    kit = armar_kit(renglones, PerfilKit.A_TU_MEDIDA.value, preferencias, elecciones=elecciones_de(punto))
    if kit.total_cop > tope or _mismos_productos(kit, ahorrador) or _mismos_productos(kit, premium):
        return None
    return kit
