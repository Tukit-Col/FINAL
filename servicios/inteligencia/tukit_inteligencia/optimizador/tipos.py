"""Vocabulario del optimizador: constantes, entidades de entrada y salida, y la aritmetica de unidades.

Decisiones:
- `MODOS_SURTIBLES` repite la lista de Catalogo porque este servicio no puede importar el otro y el
  vocabulario viaja por HTTP en el contrato.
- `TIPOS_NO_COMPRABLES` nunca van al carrito, diga lo que diga el modo; `TIPOS_NO_CONSOLIDABLES`
  (los textos) no se consolidan entre hermanos porque dos ediciones del mismo titulo no son
  sustituibles.
- `ORDEN_NIVEL` desempata y define que es subir de nivel; no se puede derivar del nombre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

ORDEN_NIVEL = ("economico", "confiable", "premium")


MODOS_SURTIBLES = frozenset({"mercado_abierto", "libro_libre"})


TIPOS_NO_COMPRABLES = frozenset({"licencia_digital", "no_comprar", "diferido", "uniforme", "otro"})


TIPOS_NO_CONSOLIDABLES = frozenset({"texto"})


MOTIVO_NO_CONSOLIDABLE = "Dos ediciones del mismo titulo no son sustituibles."


CONCEPTOS_ANCLA = ("C001", "C009", "C011", "C086")


NOTA_CONSOLIDADA = "Se compra junto con "


@dataclass(frozen=True)
class Candidato:
    sku: str
    nombre: str
    nivel: str
    precio_cop: int | None
    producto_id: str | None = None
    marca: str | None = None
    personaje: str | None = None
    imagen_url: str | None = None
    unidad_base: str = "unidad"
    unidades_por_empaque: int = 1
    atributos: dict[str, Any] = field(default_factory=dict)
    cumple: bool = True

    @property
    def rango_nivel(self) -> int:
        return ORDEN_NIVEL.index(self.nivel) if self.nivel in ORDEN_NIVEL else len(ORDEN_NIVEL)


@dataclass(frozen=True)
class Renglon:
    hijo: str
    orden: int
    texto: str
    tipo_item: str
    modo_adquisicion: str
    cantidad: int
    estado_resolucion: str
    unidad_base: str = "unidad"
    concepto_codigo: str | None = None
    concepto_nombre: str | None = None
    parecido: float = 0.0
    candidatos: tuple[Candidato, ...] = ()
    mensaje: str | None = None
    instruccion_colegio: str | None = None
    url_externa: str | None = None
    nota: str | None = None
    uno_por_estudiante: bool = False
    atributos_impuestos: dict[str, Any] = field(default_factory=dict)

    @property
    def informativa(self) -> bool:
        return self.tipo_item in TIPOS_NO_COMPRABLES or self.modo_adquisicion not in MODOS_SURTIBLES

    @property
    def no_consolidable(self) -> bool:
        return self.tipo_item in TIPOS_NO_CONSOLIDABLES


@dataclass(frozen=True)
class LineaKit:
    hijo: str
    orden: int
    descripcion: str
    tipo: str
    estado_resolucion: str
    cantidad_pedida: int
    unidad_base: str
    unidades_por_empaque: int
    unidades_a_comprar: int
    informativa: bool
    elegido: Candidato | None = None
    alternativas: tuple[Candidato, ...] = ()
    precio_unitario_cop: int | None = None
    subtotal_cop: int | None = None
    mensaje: str | None = None
    instruccion_colegio: str | None = None
    url_externa: str | None = None
    no_consolidable: bool = False
    motivo_no_consolidable: str | None = None
    concepto_codigo: str | None = None
    uno_por_estudiante: bool = False
    junto_a: int | None = None
    atributos_impuestos: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KitArmado:
    perfil: str
    total_cop: int
    objetivos: dict[str, float | int]
    lineas: tuple[LineaKit, ...]
    consolidaciones: tuple[dict[str, Any], ...] = ()
    recomendado: bool = False
    razon: str | None = None
    dentro_de_presupuesto: bool | None = None


@dataclass(frozen=True)
class SolucionFrente:
    asignacion: dict[tuple[str, int], str]
    costo: int
    fidelidad: float
    disponibilidad: float
    personaje: float


def unidades_a_comprar(cantidad_pedida: int, unidades_por_empaque: int) -> int:
    if cantidad_pedida <= 0:
        return 0
    return math.ceil(cantidad_pedida / max(1, unidades_por_empaque))


def _costo_para_ordenar(candidato: Candidato, cantidad: int) -> tuple[int, int, int]:
    if candidato.precio_cop is None:
        return (1, 0, 0)
    unidades = unidades_a_comprar(cantidad, candidato.unidades_por_empaque)
    return (0, candidato.precio_cop * unidades, candidato.precio_cop)


def _admisibles(renglon: Renglon) -> list[Candidato]:
    return [c for c in renglon.candidatos if c.cumple] or list(renglon.candidatos)
