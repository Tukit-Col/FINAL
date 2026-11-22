from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..modelos import (
    CATEGORIAS_CASO_ACUDIENTE,
    ORDEN_PRIORIDAD,
    PRIORIDAD_POR_CATEGORIA,
    SLA_HORAS,
    CategoriaCaso,
    EstadoCaso,
    Prioridad,
)

_RANGO_DESCONOCIDO = 99


@dataclass(frozen=True)
class CategoriaRechazada:
    razon: str
    estado: int


def admitir_categoria_acudiente(categoria: str) -> CategoriaCaso | CategoriaRechazada:
    try:
        elegida = CategoriaCaso(categoria)
    except ValueError:
        return CategoriaRechazada("categoria_invalida", 422)
    if elegida not in CATEGORIAS_CASO_ACUDIENTE:
        return CategoriaRechazada("categoria_no_permitida", 422)
    return elegida


def prioridad_inicial(categoria: CategoriaCaso) -> Prioridad:
    return PRIORIDAD_POR_CATEGORIA.get(categoria, Prioridad.MEDIA)


def vence_en(categoria: CategoriaCaso, desde: datetime) -> datetime | None:
    horas = SLA_HORAS.get(categoria)
    return desde + timedelta(hours=horas) if horas is not None else None


def clave_orden(prioridad: str, vence: datetime | None) -> tuple[int, float]:
    try:
        rango = ORDEN_PRIORIDAD[Prioridad(prioridad)]
    except ValueError:
        rango = _RANGO_DESCONOCIDO
    momento = vence.timestamp() if vence is not None else float("inf")
    return (rango, momento)


_C = EstadoCaso

TRANSICIONES_CASO: dict[EstadoCaso, frozenset[EstadoCaso]] = {
    _C.ABIERTO: frozenset({_C.EN_GESTION, _C.ESPERANDO_TERCERO, _C.RESUELTO}),
    _C.EN_GESTION: frozenset({_C.ESPERANDO_TERCERO, _C.RESUELTO}),
    _C.ESPERANDO_TERCERO: frozenset({_C.EN_GESTION, _C.RESUELTO}),
    _C.RESUELTO: frozenset({_C.EN_GESTION, _C.CERRADO}),
    _C.CERRADO: frozenset(),
}

LONGITUD_MAXIMA_RESPUESTA = 2000


@dataclass(frozen=True)
class CambioRechazado:
    razon: str
    estado: int
    campo: str = "estado"


def validar_cambio_estado(actual: str, destino: str) -> CambioRechazado | None:
    try:
        hacia = EstadoCaso(destino)
    except ValueError:
        return CambioRechazado("estado_invalido", 422)
    try:
        desde = EstadoCaso(actual)
    except ValueError:
        return CambioRechazado("transicion_invalida", 409)
    if hacia not in TRANSICIONES_CASO[desde]:
        return CambioRechazado("transicion_invalida", 409)
    return None


def validar_respuesta(estado: str, texto: str) -> tuple[str | None, CambioRechazado | None]:
    if estado == EstadoCaso.CERRADO.value:
        return None, CambioRechazado("caso_cerrado", 409, "texto")
    limpio = texto.strip()
    if not limpio:
        return None, CambioRechazado("respuesta_vacia", 422, "texto")
    if len(limpio) > LONGITUD_MAXIMA_RESPUESTA:
        return None, CambioRechazado("respuesta_larga", 422, "texto")
    return limpio, None


def estado_tras_respuesta(actual: str) -> str:
    return EstadoCaso.EN_GESTION.value if actual == EstadoCaso.ABIERTO.value else actual


LONGITUD_MAXIMA_NOTA = 2000


def validar_prioridad(estado: str, destino: str) -> CambioRechazado | None:
    try:
        Prioridad(destino)
    except ValueError:
        return CambioRechazado("prioridad_invalida", 422, "prioridad")
    if estado == EstadoCaso.CERRADO.value:
        return CambioRechazado("caso_cerrado", 422, "prioridad")
    return None


def validar_asignacion(
    asignar: str, asignado_actual: str | None, actor: str, *, es_admin: bool
) -> CambioRechazado | None:
    if asignar == "yo":
        return None
    if asignar == "nadie":
        if asignado_actual is not None and asignado_actual != actor and not es_admin:
            return CambioRechazado("sin_permiso", 403, "asignar")
        return None
    return CambioRechazado("asignacion_invalida", 422, "asignar")


def validar_nota(texto: str) -> tuple[str | None, CambioRechazado | None]:
    limpio = texto.strip()
    if not limpio:
        return None, CambioRechazado("nota_vacia", 422, "texto")
    if len(limpio) > LONGITUD_MAXIMA_NOTA:
        return None, CambioRechazado("nota_larga", 422, "texto")
    return limpio, None
