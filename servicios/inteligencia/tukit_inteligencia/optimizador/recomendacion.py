"""Recomendacion multicriterio (MAUT) sobre los kits y la regla de la seccion 6 del contrato."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..modelos import PESOS_POR_OMISION, PerfilKit
from .frente import _surtibles
from .preferencias import _pesos, _tope, _tope_de_a_tu_medida, quiere_a_tu_medida, quiere_fan
from .tipos import KitArmado, SolucionFrente

# Los criterios de la P21 que entran a la utilidad, con el eje del frente que
# mide cada uno. Marca exigida y calidad se leen las dos sobre la fidelidad,
# porque el frente no separa "la marca que el colegio pidio" de "la marca de
# mejor nivel": ambas suben con el nivel de marca del candidato elegido.
_CRITERIOS_MAUT = ("precio", "marca_exigida", "calidad", "personaje")


def _utilidad_normalizada(valor: float, minimo: float, maximo: float, *, creciente: bool) -> float:
    """Utilidad de un atributo en [0, 1] sobre el rango observado en el frente.

    Si todos los puntos tienen el mismo valor el atributo no distingue entre
    ellos y aporta 0 a todos.
    """
    if maximo <= minimo:
        return 0.0
    fraccion = (valor - minimo) / (maximo - minimo)
    return fraccion if creciente else 1.0 - fraccion


def elegir_recomendado_maut(
    frente: list[SolucionFrente],
    pesos: dict[str, float],
    *,
    tope: int | None = None,
    sobreprecio: float | None = None,
) -> SolucionFrente | None:
    """El punto del frente de mayor utilidad aditiva, elegido a posteriori.

    Sigue la teoria de la utilidad multiatributo (Keeney y Raiffa, 1976) en su
    uso a posteriori sobre un frente de Pareto (Miettinen, 1999, cap. 2.2):
    primero se calcula el frente y despues los pesos del acudiente escogen un
    punto. La utilidad es

        U(x) = w_precio * u_costo(x) + (w_marca_exigida + w_calidad) * u_fidelidad(x)
               + w_personaje * u_personaje(x),

    con los pesos renormalizados para que sumen 1 y cada `u` lineal en [0, 1]
    sobre el rango que el frente alcanza (`u_costo` decreciente, las demas
    crecientes). La forma aditiva supone independencia preferencial entre los
    criterios. Solo se consideran los puntos de maxima disponibilidad
    (`_surtibles`), por la misma razon que en `_proyectar`.

    `tope` y `sobreprecio` son restricciones duras: el costo no puede pasar del
    tope ni de `(1 + sobreprecio)` veces el punto mas barato. Si ningun punto
    las cumple devuelve `None`. Los empates se resuelven por menor costo, mayor
    fidelidad y mayor personaje, de modo que el resultado no depende del orden
    del frente.
    """
    if not frente:
        return None
    puntos = _surtibles(frente)
    total = sum(max(0.0, float(pesos.get(c, 0.0))) for c in _CRITERIOS_MAUT)
    w = {c: (max(0.0, float(pesos.get(c, 0.0))) / total if total > 0 else 0.0) for c in _CRITERIOS_MAUT}
    w_fidelidad = w["marca_exigida"] + w["calidad"]

    costos = [s.costo for s in puntos]
    fidelidades = [s.fidelidad for s in puntos]
    personajes = [s.personaje for s in puntos]

    rango_costo = (min(costos), max(costos))
    rango_fidelidad = (min(fidelidades), max(fidelidades))
    rango_personaje = (min(personajes), max(personajes))

    def utilidad(s: SolucionFrente) -> float:
        return (
            w["precio"] * _utilidad_normalizada(s.costo, *rango_costo, creciente=False)
            + w_fidelidad * _utilidad_normalizada(s.fidelidad, *rango_fidelidad, creciente=True)
            + w["personaje"] * _utilidad_normalizada(s.personaje, *rango_personaje, creciente=True)
        )

    validos = puntos
    if sobreprecio is not None:
        cota = (1.0 + max(0.0, sobreprecio)) * min(costos)
        validos = [s for s in validos if s.costo <= cota]
    if tope is not None:
        validos = [s for s in validos if s.costo <= tope]
    if not validos:
        return None
    return max(validos, key=lambda s: (round(utilidad(s), 12), -s.costo, s.fidelidad, s.personaje))


def _punto_de_kit(kit: KitArmado) -> SolucionFrente:
    """Un kit armado visto como punto de los cuatro ejes del frente."""
    comprables = [linea for linea in kit.lineas if not linea.informativa]
    con_personaje = sum(1 for linea in comprables if linea.elegido and linea.elegido.personaje)
    return SolucionFrente(
        {},
        kit.total_cop,
        float(kit.objetivos.get("fidelidad", 0.0)),
        float(kit.objetivos.get("disponibilidad", 0.0)),
        round(con_personaje / len(comprables), 6) if comprables else 0.0,
    )


def _mismos_productos(a: KitArmado, b: KitArmado) -> bool:
    def skus(kit: KitArmado) -> list[str | None]:
        return [linea.elegido.sku if linea.elegido else None for linea in kit.lineas]

    return skus(a) == skus(b)


def _maut_prefiere(kits: list[KitArmado], pesos: dict[str, float], kit: KitArmado) -> bool:
    """Si la utilidad aditiva de `pesos` entre los kits armados elige `kit`."""
    puntos = [_punto_de_kit(k) for k in kits]
    elegido = elegir_recomendado_maut(puntos, pesos)
    return elegido is not None and elegido is puntos[kits.index(kit)]


def recomendar(kits: list[KitArmado], preferencias: dict[str, Any]) -> list[KitArmado]:
    """Marca UNO y no oculta los demas. La regla sale de la encuesta.

    - `Fan` si el acudiente pidio un personaje: es el unico kit que lo trae.
    - `A tu Medida` si eligio el punto medio (o declaro un tope): es el kit que
      se armo para eso. Si no se armo —ninguna mejora de marca cabe, o el tope
      alcanza para el Premium entero—, la razon dice por que se marca otro.
    - Si declara al menos un 10 % de disposicion a pagar de mas, decide la
      utilidad aditiva de sus pesos entre los kits armados
      (`elegir_recomendado_maut`): sale `Premium` cuando el peso de marca y
      calidad supera al del precio sobre el rango de esos kits.
    - Por omision `Ahorrador`: 42 de 60 encuestados pagan como maximo 5 % mas
      y 15 exigen precio igual o menor.
    - Con tope, si el marcado no cabe se cae al kit de mejor marca que si quepa
      (no al mas barato); si ninguno cabe, se marca el mas barato y la razon dice
      cuanto cuesta.
    """
    if not kits:
        return kits

    pesos = {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
    sobreprecio = float(preferencias.get("disposicion_sobreprecio") or 0.0)
    tope = _tope(preferencias)

    por_perfil = {kit.perfil: kit for kit in kits}
    ahorrador = por_perfil.get(PerfilKit.AHORRADOR.value)
    premium = por_perfil.get(PerfilKit.PREMIUM.value)

    if quiere_fan(preferencias) and PerfilKit.FAN.value in por_perfil:
        elegido, razon = (
            PerfilKit.FAN.value,
            "Pediste un personaje, así que este es el kit que lo trae.",
        )
    elif PerfilKit.A_TU_MEDIDA.value in por_perfil and ahorrador and premium:
        elegido = PerfilKit.A_TU_MEDIDA.value
        tope_kit, declarado = _tope_de_a_tu_medida(preferencias, ahorrador, premium)
        razon = (
            f"Es la mejor marca que cabe en tu tope de {_pesos(tope_kit)}."
            if declarado
            else (
                "Sube de marca donde vale la pena, sin pasar de la mitad de camino al "
                f"Premium ({_pesos(tope_kit)})."
            )
        )
    elif quiere_a_tu_medida(preferencias) and ahorrador and premium:
        # Pidio el punto medio pero no hubo un kit distinto que armar.
        tope_kit, declarado = _tope_de_a_tu_medida(preferencias, ahorrador, premium)
        if premium.total_cop <= tope_kit:
            elegido = PerfilKit.PREMIUM.value
            razon = f"Tu tope de {_pesos(tope_kit)} alcanza para el kit de mejor marca."
        else:
            elegido = PerfilKit.AHORRADOR.value
            razon = (
                f"Con {_pesos(tope_kit)} no alcanza para subir de marca: este es el kit que cabe."
                if ahorrador.total_cop <= tope_kit
                else "No hay un punto medio que mejore la marca sin subir el precio."
            )
    elif sobreprecio >= 0.10 and premium and _maut_prefiere(kits, pesos, premium):
        elegido, razon = (
            PerfilKit.PREMIUM.value,
            "Con tus prioridades la marca pesa más que el precio, y aceptas pagar un poco más.",
        )
    else:
        elegido, razon = (
            PerfilKit.AHORRADOR.value,
            "Elegiste gastar lo menos posible y este es el kit más barato.",
        )
    if elegido not in por_perfil:
        elegido = kits[0].perfil

    # El presupuesto es una cota DURA, no un gusto. Es el uso mas valioso de la
    # encuesta: convierte una opinion en una restriccion que se puede imponer.
    cabe = None
    if tope is not None:
        cabe = por_perfil[elegido].total_cop <= tope
        if not cabe:
            mas_barato = min(kits, key=lambda k: k.total_cop)
            caben = [k for k in kits if k.total_cop <= tope]
            if caben:
                # La mejor marca que cabe, no la mas barata: caer al mas barato
                # dejaba el kit recomendado en el 40 % de la calidad posible.
                elegido = max(caben, key=lambda k: (k.objetivos["fidelidad"], -k.total_cop)).perfil
                razon = (
                    f"El kit que pediste se pasa de tu tope de {_pesos(tope)}, "
                    "así que te marcamos este, que sí cabe."
                )
                cabe = True
            else:
                elegido = mas_barato.perfil
                razon = (
                    f"Ningún kit cabe en tu tope de {_pesos(tope)}: el más barato que se puede "
                    f"armar con esta lista cuesta {_pesos(mas_barato.total_cop)}."
                )

    return [
        replace(
            kit,
            recomendado=kit.perfil == elegido,
            razon=razon if kit.perfil == elegido else None,
            dentro_de_presupuesto=cabe if kit.perfil == elegido else None,
        )
        for kit in kits
    ]
