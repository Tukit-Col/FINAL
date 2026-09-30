"""Las reglas del ciclo de un caso, puras y sin marco.

Cuatro decisiones que antes vivian sueltas en el manejador HTTP, aqui separadas
del router y del SQL: que categoria puede abrir un acudiente, con que prioridad
nace un caso, cuando vence segun su SLA y como se ordena la bandeja. Cada una es
una funcion que consulta las tablas de `modelos/base.py` —no las repite— y
devuelve datos planos. `admitir_categoria_acudiente` sigue el patron de
`despacho.validar_avance` de Comercio: devuelve el valor bueno o un rechazo
tipado (razon estable + codigo HTTP) que el router traduce a un `ErrorDominio`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..modelos import (
    CATEGORIAS_CASO_ACUDIENTE,
    ORDEN_PRIORIDAD,
    PRIORIDAD_POR_CATEGORIA,
    SLA_HORAS,
    CategoriaCaso,
    Prioridad,
)

_RANGO_DESCONOCIDO = 99


@dataclass(frozen=True)
class CategoriaRechazada:
    """Por que no se admite una categoria, con su codigo HTTP.

    `razon` es un identificador estable (no un mensaje): `categoria_invalida`
    cuando el texto no es ninguna categoria conocida, `categoria_no_permitida`
    cuando existe pero es una falla de la saga que abre el sistema, no una
    persona. Ambas son `422`; el router arma el sobre.
    """

    razon: str
    estado: int


def admitir_categoria_acudiente(categoria: str) -> CategoriaCaso | CategoriaRechazada:
    """La categoria que un acudiente pide, o el rechazo tipado si no procede.

    Devuelve el `CategoriaCaso` cuando el texto es una categoria valida y esta
    en `CATEGORIAS_CASO_ACUDIENTE`; si no, un `CategoriaRechazada` distinguiendo
    "no existe" de "existe pero la abre el sistema".
    """
    try:
        elegida = CategoriaCaso(categoria)
    except ValueError:
        return CategoriaRechazada("categoria_invalida", 422)
    if elegida not in CATEGORIAS_CASO_ACUDIENTE:
        return CategoriaRechazada("categoria_no_permitida", 422)
    return elegida


def prioridad_inicial(categoria: CategoriaCaso) -> Prioridad:
    """La prioridad con la que nace un caso segun su categoria (MEDIA por omision)."""
    return PRIORIDAD_POR_CATEGORIA.get(categoria, Prioridad.MEDIA)


def vence_en(categoria: CategoriaCaso, desde: datetime) -> datetime | None:
    """El instante de vencimiento del SLA, o `None` si la categoria no tiene termino."""
    horas = SLA_HORAS.get(categoria)
    return desde + timedelta(hours=horas) if horas is not None else None


def clave_orden(prioridad: str, vence: datetime | None) -> tuple[int, float]:
    """La clave de orden de la bandeja: prioridad primero, luego vencimiento.

    Se ordena por el rango de `ORDEN_PRIORIDAD` (urgente arriba) y, dentro del
    grupo, por el vencimiento mas cercano; un caso sin `vence_en` va al final de
    su grupo (+inf). Una prioridad desconocida no rompe el orden: cae al fondo
    (rango 99). Es calculo puro para que la bandeja y la etiqueta de prioridad no
    se desincronicen.
    """
    try:
        rango = ORDEN_PRIORIDAD[Prioridad(prioridad)]
    except ValueError:
        rango = _RANGO_DESCONOCIDO
    momento = vence.timestamp() if vence is not None else float("inf")
    return (rango, momento)
