"""Avance de un pedido por la cadena de entrega, como dominio puro.

Decisiones:
- La legalidad de una transicion sale de `TRANSICIONES_PEDIDO` (`modelos/base.py`), la unica fuente
  de verdad de la maquina de estados; aqui no se repite.
- `AVANCES_DE_LOGISTICA` recorta esa tabla a lo que el back-office puede mover; el webhook, el
  retracto y el barredor tienen sus propios caminos.
- `validar_avance` es pura y comprueba lo que la tabla no expresa: con reparto propio exige nombre y
  celular del repartidor, y una incidencia exige su tipo.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..modelos import EstadoPedido, transicion_valida

TIPOS_INCIDENCIA = ("no_habia_nadie", "direccion_errada", "rechazado", "otro")

_E = EstadoPedido

AVANCES_DE_LOGISTICA: dict[EstadoPedido, frozenset[EstadoPedido]] = {
    _E.PAGADO: frozenset({_E.EN_PREPARACION, _E.INCIDENCIA}),
    _E.EN_PREPARACION: frozenset({_E.DESPACHADO, _E.INCIDENCIA}),
    _E.DESPACHADO: frozenset({_E.EN_REPARTO, _E.INCIDENCIA}),
    _E.EN_REPARTO: frozenset({_E.ENTREGADO, _E.INCIDENCIA}),
    _E.INCIDENCIA: frozenset({_E.EN_PREPARACION, _E.CANCELADO}),
}

_AVISOS = {
    _E.EN_PREPARACION: "pedido_en_preparacion",
    _E.CANCELADO: "pedido_cancelado",
    _E.DESPACHADO: "pedido_despachado",
    _E.EN_REPARTO: "pedido_en_reparto",
    _E.ENTREGADO: "pedido_entregado",
    _E.INCIDENCIA: "incidencia",
}


@dataclass(frozen=True)
class AvanceRechazado:

    razon: str
    estado: int
    campo: str = "destino"


@dataclass(frozen=True)
class AvancePreparado:

    repartidor_nombre: str | None
    repartidor_celular: str | None
    tipo_incidencia: str | None
    nota: str | None
    aviso: str | None
    transportadora: str | None = None
    guia: str | None = None


def _limpio(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def _estado(valor: str) -> EstadoPedido | None:
    try:
        return EstadoPedido(valor)
    except ValueError:
        return None


def es_avance_de_logistica(actual: str, destino: str) -> bool:
    desde, hacia = _estado(actual), _estado(destino)
    if desde is None or hacia is None:
        return False
    return hacia in AVANCES_DE_LOGISTICA.get(desde, frozenset())


def validar_avance(
    actual: str,
    destino: str,
    *,
    repartidor_nombre: str | None = None,
    repartidor_celular: str | None = None,
    tipo_incidencia: str | None = None,
    nota: str | None = None,
    transportadora: str | None = None,
    guia: str | None = None,
) -> AvanceRechazado | None:
    destino_estado = _estado(destino)
    if destino_estado is None:
        return AvanceRechazado("destino_invalido", 422)

    if not (transicion_valida(actual, destino) and es_avance_de_logistica(actual, destino)):
        return AvanceRechazado("transicion_invalida", 409)

    if destino_estado is EstadoPedido.DESPACHADO:
        if _limpio(transportadora) is not None:
            if _limpio(guia) is None:
                return AvanceRechazado("despacho_sin_guia", 422, "guia")
        else:
            if _limpio(repartidor_nombre) is None:
                return AvanceRechazado("despacho_incompleto", 422, "repartidor_nombre")
            if _limpio(repartidor_celular) is None:
                return AvanceRechazado("despacho_incompleto", 422, "repartidor_celular")

    if destino_estado is EstadoPedido.INCIDENCIA:
        tipo = _limpio(tipo_incidencia)
        if tipo is None:
            return AvanceRechazado("incidencia_sin_tipo", 422, "tipo_incidencia")
        if tipo not in TIPOS_INCIDENCIA:
            return AvanceRechazado("tipo_incidencia_invalido", 422, "tipo_incidencia")
        if tipo == "otro" and _limpio(nota) is None:
            return AvanceRechazado("incidencia_sin_nota", 422, "nota")

    return None


def tipo_aviso(destino: str) -> str | None:
    estado = _estado(destino)
    return _AVISOS.get(estado) if estado is not None else None


def preparar_avance(
    destino: str,
    *,
    repartidor_nombre: str | None = None,
    repartidor_celular: str | None = None,
    tipo_incidencia: str | None = None,
    nota: str | None = None,
    transportadora: str | None = None,
    guia: str | None = None,
) -> AvancePreparado:
    estado = _estado(destino)
    despacho = estado is EstadoPedido.DESPACHADO
    incidencia = estado is EstadoPedido.INCIDENCIA
    por_transportadora = despacho and _limpio(transportadora) is not None
    return AvancePreparado(
        repartidor_nombre=_limpio(repartidor_nombre) if despacho and not por_transportadora else None,
        repartidor_celular=_limpio(repartidor_celular) if despacho and not por_transportadora else None,
        tipo_incidencia=_limpio(tipo_incidencia) if incidencia else None,
        nota=_limpio(nota),
        aviso=tipo_aviso(destino),
        transportadora=_limpio(transportadora) if por_transportadora else None,
        guia=_limpio(guia) if por_transportadora else None,
    )
