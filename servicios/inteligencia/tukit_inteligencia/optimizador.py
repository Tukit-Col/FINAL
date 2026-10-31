"""Los tres kits, ahora sobre un frente de Pareto NSGA-II (OE4).

**Que cambio y que no.** Este modulo nacio con una heuristica de seleccion por
perfil ("una regla determinista y leible en una tarde") como andamio para que
el ciclo completo corriera antes de que cada etapa fuera optima. Ese andamio ya
cumplio: el contrato esta verificado y las pantallas existen. Lo que hay aqui
ahora es el optimizador de la tesis —un NSGA-II sobre pymoo que produce un
frente de Pareto de verdad— y los tres kits son tres proyecciones de ese frente,
exactamente como la version anterior prometia ("Los tres puntos que devuelve son
comparables con los que devolveria el frente: mismo vocabulario de objetivos").

El reemplazo se hizo donde el docstring viejo dijo que se haria —en la seleccion
de candidatos— y **nada mas**. Lo que sigue siendo definitivo porque no depende
del algoritmo se conserva palabra por palabra:

- La aritmetica de unidades. `unidades_a_comprar = techo(cantidad_pedida /
  unidades_por_empaque)` es la correccion del defecto que sumaba doce cajas
  cuando la lista pedia doce lapices, y vale igual con cualquier optimizador.
- Que el total incluya solo lo que Tukit puede entregar. Una linea informativa
  se muestra y no se cobra (FU-06).
- La regla de recomendacion de la seccion 6 del contrato, que sale de la
  encuesta y no del algoritmo. **El presupuesto es una cota que se aplica
  DESPUES del frente, no dentro**: un frente de Pareto no debe esconder un kit
  valido por caro, sino ofrecerlo para que la capa de recomendacion elija con
  su explicacion (§6). Meter el presupuesto como restriccion del NSGA-II
  recortaria el frente. En cambio, el kit `A tu Medida` toma del frente ya
  calculado la mejor marca que cabe en el tope (`_armar_a_tu_medida`).

**pymoo es dependencia dura.** No hay ruta "sin pymoo": si falta, el servicio no
arranca (el import esta arriba, sin `try`). La version anterior degradaba a la
heuristica cuando pymoo no estaba, pero esa degradacion silenciosa servia kits
que no eran los del algoritmo sin avisar; fallar ruidoso en el arranque es mas
honesto que mentir en tiempo de ejecucion.

**Donde sigue viva la heuristica.** `elegir_por_perfil` NO desaparece, pero su
papel es acotado: (1) la linea de un unico candidato admisible, donde no hay
compromiso multiobjetivo que optimizar y el frente devolveria ese mismo unico
punto; y (2) la referencia contra la que la prueba de hipervolumen mide el
frente (NSGA-II no puede hacerlo peor). Nunca es el plan B de "pymoo no esta".
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from itertools import product
from typing import Any

# pymoo es la dependencia DURA del optimizador de la tesis. Se importa arriba,
# sin red: si falta, el servicio no arranca. Antes se importaba de forma
# defensiva y `armar_los_tres` caia a la heuristica cuando pymoo no estaba, pero
# esa degradacion silenciosa era un riesgo real —un despliegue mal configurado
# servia kits que no eran los del algoritmo sin decirlo—. Preferimos fallar
# ruidoso en el arranque a mentir en tiempo de ejecucion. La heuristica
# (`elegir_por_perfil`) sigue viva, pero SOLO para la linea de un unico
# candidato (no hay frente que optimizar) y como referencia de la prueba de
# hipervolumen; nunca como plan B de "pymoo no esta".
import numpy as _np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.optimize import minimize as _minimizar

from .modelos import PESOS_POR_OMISION, EstadoResolucion, PerfilKit

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

# Por encima de este tamano del espacio de busqueda (producto de candidatos por
# linea) se corre NSGA-II; por debajo se enumera el frente exacto. La
# enumeracion da el frente OPTIMO y es instantanea para kits chicos —que es lo
# que se prueba—, y el NSGA-II gana justo cuando el espacio explota, que es el
# corpus real de listas con decenas de renglones y varios candidatos cada uno.
LIMITE_ENUMERACION = 4096

# Presupuesto de busqueda del NSGA-II. Se escala con el tamano del problema —el
# numero de lineas decidibles `n` y el espacio de busqueda `espacio`— en vez de
# ser fijo, para que el frente no se quede corto en una lista de decenas de
# renglones y no gaste generaciones de mas en una de tres. Los topes evitan que
# una lista enorme dispare el tiempo del pipeline. La terminacion sigue siendo
# por numero fijo de generaciones (no por convergencia): el frente de una
# semilla dada tiene que reproducirse byte a byte, y un criterio de convergencia
# como `DefaultMultiObjectiveTermination` haria depender el corte del azar de la
# corrida. Reproducibilidad es requisito de la tesis, asi que se rechaza.
_POBLACION_MIN = 40
_POBLACION_MAX = 200
_GENERACIONES_MIN = 30
_GENERACIONES_MAX = 120


def _poblacion(n: int) -> int:
    """Tamano de poblacion escalado a las lineas decidibles, redondeado a par.

    Par porque el emparejamiento de padres de NSGA-II trabaja de a dos y una
    poblacion impar desperdicia un individuo por generacion.
    """
    cruda = min(_POBLACION_MAX, max(_POBLACION_MIN, 12 * n))
    return cruda + (cruda & 1)


def _generaciones(espacio: int) -> int:
    """Generaciones escaladas al log10 del espacio de busqueda.

    El espacio crece multiplicativamente (producto de candidatos por linea), asi
    que el esfuerzo util crece con su logaritmo, no linealmente. `max(10, ...)`
    evita `log10(0)`/valores negativos en el piso.
    """
    crudas = 20 * math.log10(max(10, espacio))
    return int(min(_GENERACIONES_MAX, max(_GENERACIONES_MIN, crudas)))


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


def elegir_por_perfil(
    candidatos: tuple[Candidato, ...],
    perfil: str,
    *,
    personajes: tuple[str, ...] = (),
    cantidad: int = 1,
) -> Candidato | None:
    """La heuristica de seleccion, hoy acotada a dos usos legitimos.

    Sigue viva por dos razones, y NINGUNA es "pymoo no esta" (pymoo es
    dependencia dura): es la eleccion de la linea sin compromiso multiobjetivo
    —un unico candidato admisible, donde el frente devolveria ese mismo punto—,
    y es la referencia contra la que se mide el frente (la prueba de
    hipervolumen exige que NSGA-II no lo haga peor). Su semantica es la de
    siempre:

    `Ahorrador` es el mas barato; `Premium` el de mejor nivel de marca y, a
    igualdad de nivel, el mas barato; `Fan` el que trae el personaje que el
    acudiente pidio para ESE hijo, y si no hay ninguno se comporta como
    `Ahorrador` en vez de inventarse un personaje.

    Nota sobre `Ahorrador`: puede terminar eligiendo un producto de nivel
    `premium` si resulto mas barato por empaque, y eso NO es un defecto. El
    nivel describe un producto y el perfil describe una ponderacion sobre el
    kit completo.

    `cantidad` es lo que pide el renglon: "mas barato" se mide sobre lo que
    cuesta la linea entera, que depende del empaque (`_costo_para_ordenar`).
    """
    admisibles = [c for c in candidatos if c.cumple] or list(candidatos)
    if not admisibles:
        return None

    def orden(c: Candidato) -> tuple[tuple[int, int, int], str]:
        return (_costo_para_ordenar(c, cantidad), c.sku)

    if perfil == PerfilKit.PREMIUM.value:
        mejor_nivel = max(c.rango_nivel for c in admisibles)
        del_nivel = [c for c in admisibles if c.rango_nivel == mejor_nivel]
        return min(del_nivel, key=orden)

    if perfil == PerfilKit.FAN.value:
        pedidos = {p.lower() for p in personajes}
        con_personaje = [
            c for c in admisibles if c.personaje and (not pedidos or c.personaje.lower() in pedidos)
        ]
        if con_personaje:
            return min(con_personaje, key=orden)

    return min(admisibles, key=orden)


# --------------------------------------------------------------- El frente


def _personajes_de(preferencias: dict[str, Any], hijo: str) -> tuple[str, ...]:
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    valores = por_hijo.get(hijo) or []
    return tuple(str(v) for v in valores)


def _objetivos_de_asignacion(
    decidibles: list[Renglon],
    elegidos: list[Candidato],
    preferencias: dict[str, Any],
) -> tuple[int, float, float, float]:
    """Los cuatro ejes de una asignacion completa, sobre lo comprable.

    - `costo`: suma de subtotales con precio conocido (los sin precio no
      inflan ni abaratan el costo; su falta se refleja en `disponibilidad`).
    - `fidelidad`: nivel de marca promedio, normalizado a [0, 1]. Es lo que
      separa un kit Premium de uno Ahorrador en el frente.
    - `disponibilidad`: fraccion de lineas cuyo candidato tiene precio, o sea
      que Tukit puede efectivamente surtir hoy.
    - `personaje`: fraccion de lineas cuyo candidato trae el personaje que el
      kit Fan buscaria. Se cuenta con la MISMA regla que `elegir_por_perfil`
      Fan: si el acudiente pidio personajes para ese hijo, solo cuenta el que
      coincide; si no pidio ninguno, cuenta cualquier personaje (el Fan es "el
      kit divertido" aunque nadie lo haya pedido explicitamente). Alinear esta
      regla con la heuristica es lo que hace que el frente no pierda el punto
      intermedio que la heuristica surtia por su cuenta.
    """
    if not decidibles:
        return (0, 0.0, 0.0, 0.0)

    costo = 0
    suma_fidelidad = 0.0
    con_precio = 0
    con_personaje = 0
    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    for renglon, elegido in zip(decidibles, elegidos, strict=True):
        unidades = unidades_a_comprar(renglon.cantidad, elegido.unidades_por_empaque)
        if elegido.precio_cop is not None:
            costo += elegido.precio_cop * unidades
            con_precio += 1
        suma_fidelidad += elegido.rango_nivel / tope_nivel
        pedidos = {p.lower() for p in _personajes_de(preferencias, renglon.hijo)}
        if elegido.personaje and (not pedidos or elegido.personaje.lower() in pedidos):
            con_personaje += 1

    n = len(decidibles)
    return (
        costo,
        round(suma_fidelidad / n, 6),
        round(con_precio / n, 6),
        round(con_personaje / n, 6),
    )


def _domina(a: tuple[int, float, float, float], b: tuple[int, float, float, float]) -> bool:
    """`a` domina a `b`: no peor en ningun eje y mejor en al menos uno.

    Se minimiza `costo` y se maximizan `fidelidad`, `disponibilidad` y
    `personaje`, asi que la comparacion mezcla sentidos: costo `<=`, el resto
    `>=`.
    """
    no_peor = a[0] <= b[0] and a[1] >= b[1] and a[2] >= b[2] and a[3] >= b[3]
    estricto = a[0] < b[0] or a[1] > b[1] or a[2] > b[2] or a[3] > b[3]
    return no_peor and estricto


def _no_dominadas(soluciones: list[SolucionFrente]) -> list[SolucionFrente]:
    """Filtra el frente de Pareto de un conjunto de soluciones.

    Se deduplica primero por vector de objetivos para no dejar copias, y se
    ordena el resultado por costo para que el frente salga estable y leible
    (dos corridas del NSGA-II con la misma semilla dan el mismo frente).
    """
    unicas: dict[tuple[int, float, float, float], SolucionFrente] = {}
    for s in soluciones:
        clave = (s.costo, s.fidelidad, s.disponibilidad, s.personaje)
        unicas.setdefault(clave, s)

    puntos = list(unicas.values())
    frente = [
        s
        for s in puntos
        if not any(
            _domina(
                (o.costo, o.fidelidad, o.disponibilidad, o.personaje),
                (s.costo, s.fidelidad, s.disponibilidad, s.personaje),
            )
            for o in puntos
            if o is not s
        )
    ]
    frente.sort(key=lambda s: (s.costo, -s.fidelidad, -s.disponibilidad, -s.personaje))
    return frente


def _solucion(
    decidibles: list[Renglon], elegidos: list[Candidato], preferencias: dict[str, Any]
) -> SolucionFrente:
    costo, fidelidad, disponibilidad, personaje = _objetivos_de_asignacion(decidibles, elegidos, preferencias)
    asignacion = {(r.hijo, r.orden): c.sku for r, c in zip(decidibles, elegidos, strict=True)}
    return SolucionFrente(asignacion, costo, fidelidad, disponibilidad, personaje)


def _frente_exacto(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
) -> list[SolucionFrente]:
    """Frente OPTIMO por enumeracion. Exacto e instantaneo para kits chicos."""
    soluciones = [_solucion(decidibles, list(combo), preferencias) for combo in product(*opciones)]
    return _no_dominadas(soluciones)


def _escalera_costo_marginal(decidibles: list[Renglon], opciones: list[list[Candidato]]) -> list[list[int]]:
    """Kits del mas barato al de mejor marca, subiendo de nivel donde cuesta menos.

    Arranca en el kit Ahorrador (el candidato de menor costo de linea en cada
    renglon) y en cada peldano sube UNA linea a un candidato de mejor nivel: la
    que tenga menor costo extra por nivel ganado. Termina cuando ninguna linea
    puede subir. Cada peldano es una asignacion (indice del candidato por linea).

    Es la regla que en el benchmark Laya vs NSGA-II dominaba algun punto del
    frente en el 68 % de las listas: con objetivos que se suman por linea, subir
    donde la marca sale mas barata recorre bien el compromiso costo-fidelidad,
    que es justo lo que SBX/PM (operadores ordinales sobre un indice nominal)
    no siempre encuentran. Por eso siembra la poblacion del NSGA-II y entra al
    filtro final del frente. Los candidatos sin precio no son peldano: su costo
    no se conoce.
    """

    def costo(i: int, j: int) -> int | None:
        c = opciones[i][j]
        if c.precio_cop is None:
            return None
        return c.precio_cop * unidades_a_comprar(decidibles[i].cantidad, c.unidades_por_empaque)

    actual = [
        min(
            range(len(o)),
            key=lambda j, i=i, o=o: (
                _costo_para_ordenar(o[j], decidibles[i].cantidad),
                -o[j].rango_nivel,
                o[j].sku,
            ),
        )
        for i, o in enumerate(opciones)
    ]
    peldanos = [list(actual)]
    while True:
        mejor: tuple[float, int, int, int] | None = None
        for i, o in enumerate(opciones):
            costo_actual = costo(i, actual[i]) or 0
            nivel_actual = o[actual[i]].rango_nivel
            for j, candidato in enumerate(o):
                costo_j = costo(i, j)
                if costo_j is None or candidato.rango_nivel <= nivel_actual:
                    continue
                extra = costo_j - costo_actual
                clave = (extra / (candidato.rango_nivel - nivel_actual), extra, i, j)
                if mejor is None or clave < mejor:
                    mejor = clave
        if mejor is None:
            return peldanos
        _, _, i, j = mejor
        actual[i] = j
        peldanos.append(list(actual))


def _poblacion_inicial(
    semillas: list[list[int]], tamanos: list[int], tamano_poblacion: int, semilla: int
) -> _np.ndarray:
    """Las asignaciones sembradas primero y el resto al azar, con la semilla fija.

    Si hay mas sembradas que cupos, se toman espaciadas a lo largo de la lista
    (la escalera va de barato a caro, y asi se conserva todo el recorrido). El
    azar sale de un generador con la misma semilla del NSGA-II, de modo que la
    poblacion —y con ella el frente— sigue reproduciendose byte a byte.
    """
    unicas = list(dict.fromkeys(tuple(s) for s in semillas))
    if len(unicas) > tamano_poblacion:
        pasos = _np.linspace(0, len(unicas) - 1, tamano_poblacion).round().astype(int)
        unicas = [unicas[k] for k in dict.fromkeys(pasos.tolist())]
    generador = _np.random.default_rng(semilla)
    faltan = tamano_poblacion - len(unicas)
    azar = (
        generador.integers(0, _np.array(tamanos), size=(faltan, len(tamanos)))
        if faltan > 0
        else _np.empty((0, len(tamanos)), dtype=int)
    )
    sembradas = _np.array(unicas, dtype=int).reshape(-1, len(tamanos))
    return _np.vstack([sembradas, azar]).astype(int)


def _frente_nsga(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
    *,
    semilla: int,
) -> list[SolucionFrente]:
    """Frente de Pareto por NSGA-II sobre pymoo. El optimizador de la tesis.

    Las variables de decision son ENTERAS en [0, n_i - 1]: la variable de la
    linea i es directamente el indice del candidato elegido. Antes eran reales
    en [0, n_i) con floor, la relajacion continua estandar, pero ahi SBX trataba
    el indice como una magnitud —interpolaba el indice 3 "entre" el 2 y el 4—
    cuando el indice es una ETIQUETA nominal, no un numero en una recta. Con
    una poblacion inicial entera + `RoundingRepair` en cruce y mutacion, la
    descendencia cae siempre en indices legales sin el epsilon de `n_i - 1e-6` y
    sin dejar de ser determinista bajo una semilla fija.

    Caveat honesto: SBX/PM con redondeo siguen siendo operadores ORDINALES sobre
    un eje nominal —asumen que indices vecinos son soluciones vecinas, que aqui
    no es cierto—. El benchmark Laya vs NSGA-II midio ese sesgo: una regla de
    subida por costo marginal dominaba algun punto del frente en el 68 % de las
    listas. Se corrige sembrando esa regla (abajo) en vez de cambiar el
    operador: la siembra entra al filtro final y garantiza que el frente no
    quede por debajo de ella, sin tocar el cruce ni la reproducibilidad.

    La poblacion inicial se siembra con las tres soluciones heuristicas
    (Ahorrador/Premium/Fan), que garantizan los extremos, y con los peldanos de
    la escalera de costo marginal (`_escalera_costo_marginal`), que recorren el
    compromiso costo-fidelidad entre ellos; el resto de la poblacion es azar con
    la misma semilla. El resultado se vuelve a filtrar por no-dominancia junto
    con todas esas semillas, asi que ningun kit sembrado puede dominar un punto
    del frente. `pop`/`gen` se escalan con el tamano del problema
    (`_poblacion`/`_generaciones`).
    """
    n = len(decidibles)
    tamanos = [len(o) for o in opciones]

    # Siembra: las tres heuristicas cubren min-costo, max-nivel y personaje,
    # que son justo los puntos que los perfiles van a proyectar; la escalera
    # cubre lo que hay entre el Ahorrador y el Premium, que es de donde sale el
    # kit recomendado con presupuesto.
    sembradas: list[list[int]] = []
    for perfil in PerfilKit:
        fila = []
        for i, r in enumerate(decidibles):
            elegido = elegir_por_perfil(
                tuple(opciones[i]),
                perfil.value,
                personajes=_personajes_de(preferencias, r.hijo),
                cantidad=r.cantidad,
            )
            fila.append(next((j for j, c in enumerate(opciones[i]) if c is elegido), 0))
        sembradas.append(fila)
    sembradas.extend(_escalera_costo_marginal(decidibles, opciones))

    def indices(x: _np.ndarray) -> list[int]:
        # Guarda de legalidad: RoundingRepair ya entrega enteros en rango, pero
        # se recorta igual para no depender de esa invariante externa.
        return [min(tamanos[i] - 1, max(0, int(round(float(x[i]))))) for i in range(n)]

    preferencias_local = preferencias

    class _ProblemaKit(Problem):
        def __init__(self) -> None:
            super().__init__(
                n_var=n,
                n_obj=4,
                n_constr=0,
                xl=_np.zeros(n, dtype=int),
                xu=_np.array([t - 1 for t in tamanos], dtype=int),
                vtype=int,
            )

        def _evaluate(self, X, out, *args, **kwargs):  # noqa: N802 (pymoo API)
            # ponytail: bucle por fila, no vectorizado. A escala tesis (pop<=200,
            # gen<=120, n de unas decenas) es sub-segundo. Una copia numpy de la
            # logica de objetivos correria el riesgo de divergir de
            # `_objetivos_de_asignacion` —justo la clase de bug que B4 arregla—,
            # asi que se reusa esa unica definicion. Vectorizar solo si el
            # perfilado lo pide.
            filas = []
            for fila in X:
                elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
                costo, fidelidad, disp, pers = _objetivos_de_asignacion(
                    decidibles, elegidos, preferencias_local
                )
                # pymoo minimiza; los tres ejes "mas es mejor" se niegan.
                filas.append([costo, -fidelidad, -disp, -pers])
            out["F"] = _np.array(filas, dtype=float)

    espacio = math.prod(tamanos)
    tamano_poblacion = _poblacion(n)
    algoritmo = NSGA2(
        pop_size=tamano_poblacion,
        sampling=_poblacion_inicial(sembradas, tamanos, tamano_poblacion, semilla),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()),
        mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )
    resultado = _minimizar(
        _ProblemaKit(),
        algoritmo,
        ("n_gen", _generaciones(espacio)),
        seed=semilla,
        verbose=False,
    )

    soluciones: list[SolucionFrente] = []
    matriz = _np.atleast_2d(resultado.X) if resultado.X is not None else _np.empty((0, n))
    for fila in matriz:
        elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    # Las sembradas entran tambien al filtro final: el NSGA-II puede perderlas
    # en el camino, y el frente no debe quedar por debajo de su propia semilla.
    for fila in sembradas:
        elegidos = [opciones[i][j] for i, j in enumerate(fila)]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    return _no_dominadas(soluciones)


def optimizar_frente(
    renglones: list[Renglon], preferencias: dict[str, Any] | None = None, *, semilla: int = 0
) -> list[SolucionFrente]:
    """El frente de Pareto de un kit. Enumera si es chico, NSGA-II si no.

    Devuelve `[]` cuando no hay un compromiso real que optimizar (ninguna linea
    decidible, o todas con un solo candidato): en ese caso `armar_los_tres` cae
    a la heuristica, que da exactamente el mismo kit sin gastar el algoritmo.
    """
    preferencias = preferencias or {}
    decidibles = [r for r in renglones if not r.informativa and _admisibles(r)]
    if not decidibles:
        return []

    opciones = [_admisibles(r) for r in decidibles]
    espacio = math.prod(len(o) for o in opciones)
    if espacio <= 1:
        return []

    if espacio <= LIMITE_ENUMERACION:
        # Enumeracion exacta para kits chicos: mismo frente que NSGA-II pero
        # exacto e instantaneo. Es una optimizacion por tamano, NO un plan B por
        # falta de pymoo (pymoo es dependencia dura).
        return _frente_exacto(decidibles, opciones, preferencias)
    return _frente_nsga(decidibles, opciones, preferencias, semilla=semilla)


def _surtibles(frente: list[SolucionFrente]) -> list[SolucionFrente]:
    """Los puntos del frente con la mayor disponibilidad que el frente alcanza.

    El costo no suma lo que no tiene precio (su falta la mide `disponibilidad`),
    asi que cambiar un candidato con precio por uno sin precio BAJA el costo y
    los dos puntos quedan en el frente sin dominarse. Proyectar sobre todo el
    frente hacia que el Ahorrador eligiera lo que no tiene precio, con un total
    que no incluia esa linea, y que el Premium y A tu Medida lo tomaran como una
    marca gratis. Es la misma regla de la heuristica (`_costo_para_ordenar`): lo
    que Tukit no puede surtir no gana una comparacion de precio, pero si una
    linea SOLO tiene candidatos sin precio, todos los puntos los llevan y la
    linea sigue saliendo.
    """
    tope = max(s.disponibilidad for s in frente)
    return [s for s in frente if s.disponibilidad == tope]


def _proyectar(frente: list[SolucionFrente], perfil: str) -> SolucionFrente | None:
    """Elige el punto del frente que corresponde a un perfil.

    Los tres perfiles son arquetipos, no los pesos del acudiente (esos solo
    deciden CUAL de los tres se recomienda, en `recomendar`). Por eso cada uno
    proyecta el frente sobre un eje distinto, entre los puntos de maxima
    disponibilidad (`_surtibles`):

    - `Ahorrador`: minimo costo.
    - `Premium`: maxima fidelidad de marca (desempata por menor costo).
    - `Fan`: maximo `personaje`; si el frente no ofrece personaje (nadie lo
      pidio), se comporta como `Ahorrador`, igual que la heuristica.
    """
    if not frente:
        return None
    frente = _surtibles(frente)
    if perfil == PerfilKit.PREMIUM.value:
        return max(frente, key=lambda s: (s.fidelidad, -s.costo, s.disponibilidad))
    if perfil == PerfilKit.FAN.value:
        mejor = max(frente, key=lambda s: (s.personaje, -s.costo, s.fidelidad))
        if mejor.personaje > 0:
            return mejor
        # Sin personaje pedido, Fan es Ahorrador: no inventa un personaje.
    return min(frente, key=lambda s: (s.costo, -s.disponibilidad, -s.fidelidad))


def _linea_desde(renglon: Renglon, elegido: Candidato | None) -> LineaKit:
    """Construye la linea del kit a partir del candidato ya elegido.

    Separa la CONSTRUCCION de la linea de la SELECCION del candidato: la
    seleccion la hace el frente (o la heuristica en la linea de un solo
    candidato) y este helper solo arma la fila con la aritmetica de unidades y
    el subtotal. Es la pieza que no cambia con el algoritmo.
    """
    if renglon.informativa:
        # Ni precio ni subtotal, y la base lo impone con un CHECK. Lo que si
        # lleva es la instruccion textual del colegio: decir "esto lo vende la
        # editorial el 24 de enero en el colegio" es util; callarlo deja al
        # acudiente con un hueco que descubre tarde.
        return LineaKit(
            hijo=renglon.hijo,
            orden=renglon.orden,
            descripcion=renglon.texto,
            tipo=renglon.tipo_item,
            estado_resolucion=renglon.estado_resolucion,
            cantidad_pedida=renglon.cantidad,
            unidad_base=renglon.unidad_base,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            informativa=True,
            mensaje=renglon.mensaje or renglon.nota,
            instruccion_colegio=renglon.instruccion_colegio,
            url_externa=renglon.url_externa,
            no_consolidable=renglon.no_consolidable,
            motivo_no_consolidable=MOTIVO_NO_CONSOLIDABLE if renglon.no_consolidable else None,
            concepto_codigo=renglon.concepto_codigo,
        )

    if elegido is None:
        return LineaKit(
            hijo=renglon.hijo,
            orden=renglon.orden,
            descripcion=renglon.texto,
            tipo=renglon.tipo_item,
            estado_resolucion=renglon.estado_resolucion,
            cantidad_pedida=renglon.cantidad,
            unidad_base=renglon.unidad_base,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            informativa=False,
            mensaje=renglon.mensaje,
            concepto_codigo=renglon.concepto_codigo,
        )

    unidades = unidades_a_comprar(renglon.cantidad, elegido.unidades_por_empaque)
    subtotal = None if elegido.precio_cop is None else elegido.precio_cop * unidades
    alternativas = tuple(c for c in renglon.candidatos if c.sku != elegido.sku)[:2]

    return LineaKit(
        hijo=renglon.hijo,
        orden=renglon.orden,
        descripcion=renglon.texto,
        tipo=renglon.tipo_item,
        estado_resolucion=renglon.estado_resolucion,
        cantidad_pedida=renglon.cantidad,
        unidad_base=elegido.unidad_base or renglon.unidad_base,
        unidades_por_empaque=elegido.unidades_por_empaque,
        unidades_a_comprar=unidades,
        informativa=False,
        elegido=elegido,
        alternativas=alternativas,
        precio_unitario_cop=elegido.precio_cop,
        subtotal_cop=subtotal,
        mensaje=renglon.mensaje,
        no_consolidable=renglon.no_consolidable,
        motivo_no_consolidable=MOTIVO_NO_CONSOLIDABLE if renglon.no_consolidable else None,
        concepto_codigo=renglon.concepto_codigo,
        uno_por_estudiante=renglon.uno_por_estudiante,
    )


def juntar_herramientas(lineas: tuple[LineaKit, ...]) -> tuple[LineaKit, ...]:
    """Una herramienta que varias materias piden se compra una vez por hijo.

    Las listas se escriben por materia, y cada profesor pide lo que usa: las
    tijeras salen en artes, en tecnologia y en la cartuchera. Son las mismas
    tijeras, y el kit cobraba tres. En las 18 listas curadas, 43 renglones de
    herramientas repetian a otro identico (Decimo pedia tres calculadoras
    cientificas).

    Solo para conceptos `uno_por_estudiante` (lo dice el catalogo): lo que se
    gasta (pegante, cinta, cuadernos) puede ser uno por materia a proposito, y
    juntarlo dejaria al nino sin material. Dentro de un MISMO hijo: dos
    hermanos necesitan cada uno sus tijeras (eso lo decide `consolidar`, por
    empaque). Y sobre el PRODUCTO elegido: `regla` y `regla de acero` no son la
    misma compra.

    Se compra la cantidad mayor, no la suma: si artes pide dos reglas y la
    cartuchera una, dos alcanzan. La linea repetida sigue en el kit con cero
    unidades y dice donde quedo, igual que la de un hermano consolidado: el
    colegio la pidio y el acudiente tiene que poder encontrarla.
    """
    grupos: dict[tuple[str, str], list[int]] = {}
    for indice, linea in enumerate(lineas):
        if linea.elegido is None or linea.informativa or not linea.uno_por_estudiante:
            continue
        grupos.setdefault((linea.hijo, linea.elegido.sku), []).append(indice)

    resultado = list(lineas)
    for indices in grupos.values():
        if len(indices) < 2:
            continue
        primera = lineas[indices[0]]
        cantidad = max(lineas[i].cantidad_pedida for i in indices)
        unidades = unidades_a_comprar(cantidad, primera.unidades_por_empaque)
        precio = primera.precio_unitario_cop
        resultado[indices[0]] = replace(
            primera,
            unidades_a_comprar=unidades,
            subtotal_cop=None if precio is None else precio * unidades,
        )
        for i in indices[1:]:
            otra = lineas[i]
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                junto_a=primera.orden,
                mensaje=f"Ya va en la linea {primera.orden}: sirve para todas las materias.",
            )
    return tuple(resultado)


def consolidar(lineas: tuple[LineaKit, ...]) -> tuple[tuple[LineaKit, ...], tuple[dict[str, Any], ...]]:
    """Junta la demanda de varios hermanos sobre el mismo producto.

    Es la razon de que el trabajo sea por HOGAR y no por hijo: si cada hijo se
    pidiera aparte, nadie podria ver que dos ninos necesitan un borrador cada
    uno y que una caja de diez sale mejor que dos sueltos.

    La consolidacion se hace sobre el PRODUCTO elegido, no sobre el concepto.
    Dos hermanos a los que se les eligio el mismo sku comparten empaque; dos a
    los que se les eligio productos distintos, no, y forzarlo cambiaria lo que
    cada uno recibe sin decirlo.

    El ahorro se le imputa a la primera linea del grupo y las demas quedan en
    cero unidades con su explicacion. Se prefiere eso a borrarlas porque el
    acudiente pidio ese item para ese hijo y tiene que seguir viendolo.
    """
    grupos: dict[str, list[int]] = {}
    for indice, linea in enumerate(lineas):
        if linea.elegido is None or linea.informativa or linea.no_consolidable or linea.junto_a is not None:
            continue
        grupos.setdefault(linea.elegido.sku, []).append(indice)

    resultado = list(lineas)
    notas: list[dict[str, Any]] = []

    for sku, indices in grupos.items():
        if len(indices) < 2:
            continue
        hijos = sorted({lineas[i].hijo for i in indices})
        if len(hijos) < 2:
            continue

        primera = lineas[indices[0]]
        empaque = primera.unidades_por_empaque
        demanda = sum(lineas[i].cantidad_pedida for i in indices)
        juntas = unidades_a_comprar(demanda, empaque)
        sueltas = sum(lineas[i].unidades_a_comprar for i in indices)
        if juntas >= sueltas:
            # Sin ahorro no se toca nada. Consolidar por consolidar movería
            # unidades entre hermanos sin beneficio y volveria la explicacion
            # mas dificil de leer que la lista original.
            continue

        precio = primera.precio_unitario_cop
        ahorro = 0 if precio is None else precio * (sueltas - juntas)

        resultado[indices[0]] = replace(
            primera,
            unidades_a_comprar=juntas,
            subtotal_cop=None if precio is None else precio * juntas,
        )
        # El texto lo lee el acudiente: nunca el id interno del hijo ("hijo-1").
        # Se nombra la linea que si se compra, y de quien es si no es de este
        # mismo hijo (el grupo puede traer dos renglones del mismo hijo).
        para_quienes = "los dos" if len(indices) == 2 else "todos"
        de_otro = "tu otro hijo" if len(hijos) == 2 else "otro de tus hijos"
        for i in indices[1:]:
            otra = lineas[i]
            donde = f"la línea {primera.orden}" + ("" if otra.hijo == primera.hijo else f" de {de_otro}")
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                mensaje=f"Se compra junto con {donde}: un empaque de {empaque} alcanza para {para_quienes}.",
            )

        notas.append(
            {
                "sku": sku,
                "producto": primera.elegido.nombre if primera.elegido else sku,
                "hijos": hijos,
                "demanda_base": demanda,
                "unidades_a_comprar": juntas,
                "ahorro": ahorro,
                "explicacion": (f"Un empaque de {empaque} sale mas barato que {sueltas} por separado."),
            }
        )

    return tuple(resultado), tuple(notas)


def _objetivos(lineas: tuple[LineaKit, ...], total: int) -> dict[str, float | int]:
    """El resumen de display del kit, calculado solo sobre lo comprable.

    Medir sobre las lineas informativas inflaria los numeros con items que Tukit
    nunca iba a surtir, y el kit se veria mejor cuanto mas cosas no pudiera vender.

    `fidelidad` es EL MISMO eje que el frente optimiza: nivel de marca promedio
    normalizado a [0, 1], recomputado aqui desde el `rango_nivel` del candidato
    elegido en cada linea. Antes este `fidelidad` era otra cosa —la fraccion de
    lineas resueltas en automatico—, con lo que el numero que se mostraba no era
    el eje que se habia optimizado; los dos solo coincidian por correlacion. Esa
    fraccion sigue siendo util y se reporta aparte como `resolucion_auto`.
    """
    comprables = [linea for linea in lineas if not linea.informativa]
    if not comprables:
        return {
            "costo": total,
            "fidelidad": 0.0,
            "disponibilidad": 0.0,
            "resolucion_auto": 0.0,
        }

    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    suma_fidelidad = sum((linea.elegido.rango_nivel / tope_nivel) for linea in comprables if linea.elegido)
    resueltas = sum(
        1 for linea in comprables if linea.estado_resolucion == EstadoResolucion.RESUELTO_AUTO.value
    )
    con_precio = sum(1 for linea in comprables if linea.precio_unitario_cop is not None)
    return {
        "costo": total,
        "fidelidad": round(suma_fidelidad / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
        "resolucion_auto": round(resueltas / len(comprables), 3),
    }


def armar_kit(
    renglones: list[Renglon],
    perfil: str,
    preferencias: dict[str, Any],
    *,
    elecciones: dict[tuple[str, int], Candidato] | None = None,
) -> KitArmado:
    """Arma un kit para un perfil.

    Si `elecciones` viene (proyeccion del frente de Pareto), se usa el candidato
    que el frente asigno a cada linea; si no, se cae a la heuristica por perfil.
    La diferencia es solo la SELECCION del candidato: unidades, consolidacion,
    total honesto y objetivos son identicos en las dos rutas.
    """
    lineas_lista: list[LineaKit] = []
    for renglon in renglones:
        if renglon.informativa:
            lineas_lista.append(_linea_desde(renglon, None))
            continue
        if elecciones is not None:
            elegido = elecciones.get((renglon.hijo, renglon.orden))
        else:
            elegido = elegir_por_perfil(
                renglon.candidatos,
                perfil,
                personajes=_personajes_de(preferencias, renglon.hijo),
                cantidad=renglon.cantidad,
            )
        lineas_lista.append(_linea_desde(renglon, elegido))

    lineas, consolidaciones = consolidar(juntar_herramientas(tuple(lineas_lista)))
    # El total suma SOLO lo no informativo. Es la promesa de la seccion 5.1.1
    # del contrato y la que impide cobrar lo que no se puede entregar.
    total = sum(linea.subtotal_cop or 0 for linea in lineas if not linea.informativa)
    return KitArmado(
        perfil=perfil,
        total_cop=total,
        objetivos=_objetivos(lineas, total),
        lineas=lineas,
        consolidaciones=consolidaciones,
    )


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


def _mismos_productos(a: KitArmado, b: KitArmado) -> bool:
    def skus(kit: KitArmado) -> list[str | None]:
        return [linea.elegido.sku if linea.elegido else None for linea in kit.lineas]

    return skus(a) == skus(b)


def recomendar(kits: list[KitArmado], preferencias: dict[str, Any]) -> list[KitArmado]:
    """Marca UNO y no oculta los demas. La regla sale de la encuesta.

    - `Fan` si el acudiente pidio un personaje: es el unico kit que lo trae.
    - `A tu Medida` si eligio el punto medio (o declaro un tope): es el kit que
      se armo para eso. Si no se armo —ninguna mejora de marca cabe, o el tope
      alcanza para el Premium entero—, la razon dice por que se marca otro.
    - `Premium` si pone la calidad primero Y declara al menos un 10 % de
      disposicion a pagar de mas.
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
    calidad_primero = pesos.get("calidad", 0) >= max(
        pesos.get("precio", 0), pesos.get("marca_exigida", 0), pesos.get("personaje", 0)
    )

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
    elif calidad_primero and sobreprecio >= 0.10 and premium:
        elegido, razon = (
            PerfilKit.PREMIUM.value,
            "Pusiste la calidad primero y aceptas pagar un poco más.",
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


def anclar_personaje(kit: KitArmado, personaje: str | None) -> KitArmado:
    """Sube al tope las 4 lineas ancla cuyo producto trae el personaje pedido.

    Es post-proceso puro sobre un kit ya armado: NSGA-II no se toca. Cuando el
    acudiente pidio un personaje para el hijo, las lineas de los cuatro
    conceptos ancla (`CONCEPTOS_ANCLA`) cuyo producto elegido es de ese
    personaje se mueven al frente en el orden canonico cuaderno -> cartuchera
    -> carpeta -> maleta; el resto de las lineas conserva su orden. Como solo
    reordena, `total_cop`, `consolidaciones` y objetivos no cambian (el total
    es una suma, no depende del orden), y se defiende con una prueba.

    Si `personaje` es None o ninguna linea ancla trae ese personaje, devuelve
    el kit sin tocar (mismo objeto cuando es None).
    """
    if personaje is None:
        return kit

    pedido = personaje.lower()

    def es_ancla(linea: LineaKit, codigo: str) -> bool:
        return (
            not linea.informativa
            and linea.concepto_codigo == codigo
            and linea.elegido is not None
            and (linea.elegido.personaje or "").lower() == pedido
        )

    anclas: list[LineaKit] = []
    usadas: set[int] = set()
    for codigo in CONCEPTOS_ANCLA:
        for indice, linea in enumerate(kit.lineas):
            if indice not in usadas and es_ancla(linea, codigo):
                anclas.append(linea)
                usadas.add(indice)

    if not anclas:
        return kit

    resto = [linea for indice, linea in enumerate(kit.lineas) if indice not in usadas]
    return replace(kit, lineas=tuple(anclas) + tuple(resto))
