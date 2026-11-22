"""Vocabulario del optimizador: constantes, entidades de entrada/salida y la aritmetica de unidades."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Orden de calidad de marca. Se usa para desempatar y para saber que es "subir
# de nivel"; no se puede derivar del nombre, asi que vive aqui.
ORDEN_NIVEL = ("economico", "confiable", "premium")


# Los modos en los que Tukit puede poner el item en el carrito. Es la misma
# lista que `catalogo.modelos.MODOS_SURTIBLES`, repetida aqui porque este
# servicio no puede importar el otro (invariante 1) y porque el vocabulario
# viaja por HTTP en el contrato, no por un paquete compartido.
MODOS_SURTIBLES = frozenset({"mercado_abierto", "libro_libre"})


# Tipos de renglon que nunca van al carrito, dijera lo que dijera el modo.
# `otro` es lo que el colegio pide y Tukit decidio no vender (audifonos, un
# titere): el acudiente lo compra por su cuenta. Sin estar aqui, la linea salia
# como un producto que faltaba en vez de una nota que dice que hacer.
TIPOS_NO_COMPRABLES = frozenset({"licencia_digital", "no_comprar", "diferido", "uniforme", "otro"})


# Dos ediciones del mismo titulo NO son sustituibles, asi que los textos no se
# consolidan entre hermanos aunque el titulo coincida. Es la regla inversa de
# la consolidacion y se enuncia como dato para poder explicarla en la linea.
TIPOS_NO_CONSOLIDABLES = frozenset({"texto"})


MOTIVO_NO_CONSOLIDABLE = "Dos ediciones del mismo titulo no son sustituibles."


# Los cuatro conceptos que el acudiente ve como "los del personaje": cuaderno,
# cartuchera, carpeta y maleta. Cuando pidio un personaje para un hijo, estas
# lineas suben al tope del kit en ESTE orden canonico —es puro reordenamiento
# de presentacion, no cambia que producto se eligio ni cuanto cuesta el kit.
CONCEPTOS_ANCLA = ("C001", "C009", "C011", "C086")


# Prefijo de la nota que `consolidar` le pone a la linea que se compra junto con
# otra; `dominio.pipeline` la reconoce para borrarla cuando el grupo se deshace.
NOTA_CONSOLIDADA = "Se compra junto con "


@dataclass(frozen=True)
class Candidato:
    """Un producto que el catalogo ofrecio para un renglon."""

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
    """Un renglon ya parseado y ya emparejado, listo para entrar a un kit."""

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
    # El concepto dura todo el ano y sirve para todas las materias (tijeras,
    # regla, colores). Lo dice el catalogo; ver `juntar_herramientas`.
    uno_por_estudiante: bool = False
    # Lo que el renglon EXIGE (`encuadernacion=cosido`, `rayado=cuadriculado`).
    # El kit Fan lo necesita para no poner un producto de personaje que el
    # colegio no acepta en ese renglon (un argollado donde pidio cosido).
    atributos_impuestos: dict[str, Any] = field(default_factory=dict)

    @property
    def informativa(self) -> bool:
        """Se muestra y no se cobra.

        Dos caminos distintos llevan aqui y los dos importan: el TIPO de
        renglon (una licencia digital nunca va al carrito) y el MODO de
        adquisicion (un texto de edicion exclusiva es papel comprable, pero el
        colegio cerro quien lo vende). Colapsarlos perderia el segundo, que es
        justo el que hace la diferencia entre un catalogo que promete y uno
        que cumple.
        """
        return self.tipo_item in TIPOS_NO_COMPRABLES or self.modo_adquisicion not in MODOS_SURTIBLES

    @property
    def no_consolidable(self) -> bool:
        return self.tipo_item in TIPOS_NO_CONSOLIDABLES


@dataclass(frozen=True)
class LineaKit:
    """Una linea ya resuelta para un perfil concreto."""

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
    # El orden de la linea en la que ya va este producto, si se junto.
    junto_a: int | None = None
    # Lo que el renglon exigia; viaja a la linea para decidir donde cabe el
    # producto de personaje del Fan (ver `lineas_con_personaje`).
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
    """Un punto del frente de Pareto: una asignacion de candidato por linea.

    Guarda los tres ejes del contrato (`costo`, `fidelidad`, `disponibilidad`)
    mas `personaje`, que es lo que le da al kit Fan un punto propio en el frente
    cuando el acudiente pidio un personaje. `asignacion` mapea la clave de linea
    `(hijo, orden)` al SKU elegido, para reconstruir el kit sin re-optimizar.
    """

    asignacion: dict[tuple[str, int], str]
    costo: int
    fidelidad: float
    disponibilidad: float
    personaje: float


def unidades_a_comprar(cantidad_pedida: int, unidades_por_empaque: int) -> int:
    """Techo de la division. La correccion del error de carrito, en una linea.

    El empaque nunca es cero: la base lo impide con un CHECK, y aqui se vuelve
    a defender porque una division por cero en el armado del kit seria un 500
    en la unica pantalla que el acudiente esperaba durante tres minutos.
    """
    if cantidad_pedida <= 0:
        return 0
    return math.ceil(cantidad_pedida / max(1, unidades_por_empaque))


def _costo_para_ordenar(candidato: Candidato, cantidad: int) -> tuple[int, int, int]:
    """Los que tienen precio primero y de menor a mayor costo de LINEA.

    Se compara lo que cuesta la linea (precio x unidades a comprar), no el
    precio unitario: doce lapices sueltos a $1.000 cuestan mas que una caja de
    doce a $9.000. Ordenar por precio unitario hacia que el Ahorrador fallara en
    el 20 % de las listas del benchmark Laya vs NSGA-II. A igual costo de linea
    desempata el precio unitario.

    Un candidato sin precio no se descarta: puede ser el unico que cumple el
    atributo que el colegio exigio, y ofrecerlo diciendo "no conocemos el
    precio" es mejor respuesta que no ofrecer nada. Lo que no puede es ganar
    una comparacion de precio, y por eso va al final del orden.
    """
    if candidato.precio_cop is None:
        return (1, 0, 0)
    unidades = unidades_a_comprar(cantidad, candidato.unidades_por_empaque)
    return (0, candidato.precio_cop * unidades, candidato.precio_cop)


def _admisibles(renglon: Renglon) -> list[Candidato]:
    """Los candidatos que se pueden elegir para un renglon.

    Mismo criterio que la heuristica: se prefieren los que cumplen el atributo
    exigido, pero si ninguno cumple no se deja el renglon vacio —el que no
    cumple entra como ultimo recurso, con su bandera intacta.
    """
    return [c for c in renglon.candidatos if c.cumple] or list(renglon.candidatos)
