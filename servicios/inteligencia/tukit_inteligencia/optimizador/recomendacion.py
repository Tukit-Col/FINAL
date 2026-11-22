from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..modelos import PESOS_POR_OMISION, PerfilKit
from .frente import _surtibles
from .preferencias import _pesos, _tope, _tope_de_a_tu_medida, quiere_a_tu_medida, quiere_fan
from .tipos import KitArmado, SolucionFrente

_CRITERIOS_MAUT = ("precio", "marca_exigida", "calidad", "personaje")


def _utilidad_normalizada(valor: float, minimo: float, maximo: float, *, creciente: bool) -> float:
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
    puntos = [_punto_de_kit(k) for k in kits]
    elegido = elegir_recomendado_maut(puntos, pesos)
    return elegido is not None and elegido is puntos[kits.index(kit)]


def recomendar(kits: list[KitArmado], preferencias: dict[str, Any]) -> list[KitArmado]:
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

    cabe = None
    if tope is not None:
        cabe = por_perfil[elegido].total_cop <= tope
        if not cabe:
            mas_barato = min(kits, key=lambda k: k.total_cop)
            caben = [k for k in kits if k.total_cop <= tope]
            if caben:
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
