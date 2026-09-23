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
  encuesta y no del algoritmo. **El presupuesto es una cota que vive en
  `recomendar`, no en el frente**: un frente de Pareto no debe esconder un kit
  valido por caro, sino ofrecerlo para que la capa de recomendacion lo degrade
  con su explicacion (§6). Meter el presupuesto como restriccion del NSGA-II
  cambiaria la composicion del kit Premium y romperia esa regla.

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
from pymoo.operators.sampling.rnd import FloatRandomSampling
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
TIPOS_NO_COMPRABLES = frozenset({"licencia_digital", "no_comprar", "diferido", "uniforme"})

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

# Presupuesto de busqueda del NSGA-II. Se escala con el numero de lineas
# decidibles para que el frente no se quede corto en listas grandes, con topes
# para que una lista enorme no dispare el tiempo del pipeline.
_POBLACION = 60
_GENERACIONES = 40


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


def _precio_para_ordenar(candidato: Candidato) -> tuple[int, int]:
    """Los que tienen precio primero y de menor a mayor.

    Un candidato sin precio no se descarta: puede ser el unico que cumple el
    atributo que el colegio exigio, y ofrecerlo diciendo "no conocemos el
    precio" es mejor respuesta que no ofrecer nada. Lo que no puede es ganar
    una comparacion de precio, y por eso va al final del orden.
    """
    return (1, 0) if candidato.precio_cop is None else (0, candidato.precio_cop)


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
    """
    admisibles = [c for c in candidatos if c.cumple] or list(candidatos)
    if not admisibles:
        return None

    if perfil == PerfilKit.PREMIUM.value:
        mejor_nivel = max(c.rango_nivel for c in admisibles)
        del_nivel = [c for c in admisibles if c.rango_nivel == mejor_nivel]
        return min(del_nivel, key=lambda c: (_precio_para_ordenar(c), c.sku))

    if perfil == PerfilKit.FAN.value:
        pedidos = {p.lower() for p in personajes}
        con_personaje = [
            c for c in admisibles if c.personaje and (not pedidos or c.personaje.lower() in pedidos)
        ]
        if con_personaje:
            return min(con_personaje, key=lambda c: (_precio_para_ordenar(c), c.sku))

    return min(admisibles, key=lambda c: (_precio_para_ordenar(c), c.sku))


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
            _domina((o.costo, o.fidelidad, o.disponibilidad, o.personaje),
                     (s.costo, s.fidelidad, s.disponibilidad, s.personaje))
            for o in puntos
            if o is not s
        )
    ]
    frente.sort(key=lambda s: (s.costo, -s.fidelidad, -s.disponibilidad, -s.personaje))
    return frente


def _solucion(
    decidibles: list[Renglon], elegidos: list[Candidato], preferencias: dict[str, Any]
) -> SolucionFrente:
    costo, fidelidad, disponibilidad, personaje = _objetivos_de_asignacion(
        decidibles, elegidos, preferencias
    )
    asignacion = {(r.hijo, r.orden): c.sku for r, c in zip(decidibles, elegidos, strict=True)}
    return SolucionFrente(asignacion, costo, fidelidad, disponibilidad, personaje)


def _frente_exacto(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
) -> list[SolucionFrente]:
    """Frente OPTIMO por enumeracion. Exacto e instantaneo para kits chicos."""
    soluciones = [
        _solucion(decidibles, list(combo), preferencias) for combo in product(*opciones)
    ]
    return _no_dominadas(soluciones)


def _frente_nsga(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
    *,
    semilla: int,
) -> list[SolucionFrente]:
    """Frente de Pareto por NSGA-II sobre pymoo. El optimizador de la tesis.

    Las variables de decision son reales en [0, n_i) y se redondean al indice
    del candidato de la linea i; es la codificacion continua estandar para un
    problema combinatorio y le deja a los operadores SBX/PM hacer su trabajo. La
    poblacion inicial se siembra con las tres soluciones heuristicas
    (Ahorrador/Premium/Fan) para garantizar que el frente cubra los extremos
    aunque la muestra aleatoria no los toque, y el resultado se vuelve a filtrar
    por no-dominancia junto con esas semillas.
    """
    n = len(decidibles)
    tamanos = [len(o) for o in opciones]

    def indices(x: _np.ndarray) -> list[int]:
        return [min(tamanos[i] - 1, max(0, int(math.floor(x[i])))) for i in range(n)]

    preferencias_local = preferencias

    class _ProblemaKit(Problem):
        def __init__(self) -> None:
            super().__init__(
                n_var=n,
                n_obj=4,
                n_constr=0,
                xl=_np.zeros(n),
                # El tope es n_i - epsilon para que floor nunca caiga en n_i.
                xu=_np.array([t - 1e-6 for t in tamanos], dtype=float),
            )

        def _evaluate(self, X, out, *args, **kwargs):  # noqa: N802 (pymoo API)
            filas = []
            for fila in X:
                elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
                costo, fidelidad, disp, pers = _objetivos_de_asignacion(
                    decidibles, elegidos, preferencias_local
                )
                # pymoo minimiza; los tres ejes "mas es mejor" se niegan.
                filas.append([costo, -fidelidad, -disp, -pers])
            out["F"] = _np.array(filas, dtype=float)

    algoritmo = NSGA2(
        pop_size=_POBLACION,
        sampling=FloatRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )
    resultado = _minimizar(
        _ProblemaKit(),
        algoritmo,
        ("n_gen", _GENERACIONES),
        seed=semilla,
        verbose=False,
    )

    soluciones: list[SolucionFrente] = []
    matriz = _np.atleast_2d(resultado.X) if resultado.X is not None else _np.empty((0, n))
    for fila in matriz:
        elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    # Siembra: las tres heuristicas garantizan cubrir min-costo, max-nivel y
    # personaje, que son justo los puntos que los perfiles van a proyectar.
    for perfil in PerfilKit:
        elegidos = [
            elegir_por_perfil(
                tuple(opciones[i]), perfil.value, personajes=_personajes_de(preferencias, r.hijo)
            )
            or opciones[i][0]
            for i, r in enumerate(decidibles)
        ]
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


def _proyectar(frente: list[SolucionFrente], perfil: str) -> SolucionFrente | None:
    """Elige el punto del frente que corresponde a un perfil.

    Los tres perfiles son arquetipos, no los pesos del acudiente (esos solo
    deciden CUAL de los tres se recomienda, en `recomendar`). Por eso cada uno
    proyecta el frente sobre un eje distinto:

    - `Ahorrador`: minimo costo (desempata por mayor disponibilidad).
    - `Premium`: maxima fidelidad de marca (desempata por menor costo).
    - `Fan`: maximo `personaje`; si el frente no ofrece personaje (nadie lo
      pidio), se comporta como `Ahorrador`, igual que la heuristica.
    """
    if not frente:
        return None
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
    )


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
        if linea.elegido is None or linea.informativa or linea.no_consolidable:
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
        for i in indices[1:]:
            otra = lineas[i]
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                mensaje=(
                    f"Se compra junto con el de {primera.hijo}: un empaque de {empaque} alcanza para los dos."
                ),
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
    """Los tres ejes del frente, calculados solo sobre lo comprable.

    Medir fidelidad o disponibilidad sobre las lineas informativas inflaria
    los dos numeros con items que Tukit nunca iba a surtir, y el kit se veria
    mejor cuanto mas cosas no pudiera vender.
    """
    comprables = [linea for linea in lineas if not linea.informativa]
    if not comprables:
        return {"costo": total, "fidelidad": 0.0, "disponibilidad": 0.0}

    resueltas = sum(
        1 for linea in comprables if linea.estado_resolucion == EstadoResolucion.RESUELTO_AUTO.value
    )
    con_precio = sum(1 for linea in comprables if linea.precio_unitario_cop is not None)
    return {
        "costo": total,
        "fidelidad": round(resueltas / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
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
                renglon.candidatos, perfil, personajes=_personajes_de(preferencias, renglon.hijo)
            )
        lineas_lista.append(_linea_desde(renglon, elegido))

    lineas, consolidaciones = consolidar(tuple(lineas_lista))
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


def recomendar(kits: list[KitArmado], preferencias: dict[str, Any]) -> list[KitArmado]:
    """Marca UNO y no oculta los otros dos. La regla sale de la encuesta.

    - Por omision `Ahorrador`: 42 de 60 encuestados pagan como maximo 5 % mas
      y 15 exigen precio igual o menor.
    - `Premium` solo si el acudiente pone calidad primero Y declara al menos
      un 10 % de disposicion a pagar de mas.
    - `Fan` solo con `personaje_por_hijo` explicito. El personaje quedo ultimo
      en la P21, y tiene sentido: el que paga es el papa y el que quiere el
      personaje es el hijo.
    - Si el recomendado excede el presupuesto, se cae al siguiente kit que si
      quepa y la razon lo dice.
    """
    if not kits:
        return kits

    pesos = {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
    presupuesto = preferencias.get("presupuesto_por_hijo")
    sobreprecio = float(preferencias.get("disposicion_sobreprecio") or 0.0)
    personajes = preferencias.get("personaje_por_hijo") or {}

    por_perfil = {kit.perfil: kit for kit in kits}
    calidad_primero = pesos.get("calidad", 0) >= max(
        pesos.get("precio", 0), pesos.get("marca_exigida", 0), pesos.get("personaje", 0)
    )

    if personajes and pesos.get("personaje", 0) > 0 and PerfilKit.FAN.value in por_perfil:
        elegido, razon = (
            PerfilKit.FAN.value,
            "Pediste personajes para tus hijos, asi que este es el kit que los incluye.",
        )
    elif calidad_primero and sobreprecio >= 0.10 and PerfilKit.PREMIUM.value in por_perfil:
        elegido, razon = (
            PerfilKit.PREMIUM.value,
            "Pusiste la calidad primero y aceptas pagar hasta un 10 % mas.",
        )
    else:
        elegido, razon = (
            PerfilKit.AHORRADOR.value,
            "Elegiste precio como lo mas importante y este es el kit mas barato.",
        )

    # El presupuesto es una cota DURA, no un gusto. Es el uso mas valioso de la
    # encuesta: convierte una opinion en una restriccion que se puede imponer.
    cabe = None
    if isinstance(presupuesto, int) and presupuesto > 0:
        tope = int(presupuesto * max(1.0, 1.0 + sobreprecio))
        cabe = por_perfil[elegido].total_cop <= tope
        if not cabe:
            mas_barato = min(kits, key=lambda k: k.total_cop)
            if mas_barato.total_cop <= tope:
                elegido = mas_barato.perfil
                razon = (
                    f"El kit que pediste se pasa de tu presupuesto de ${presupuesto:,}, "
                    f"asi que te recomiendo este, que si cabe."
                )
                cabe = True
            else:
                razon = (
                    f"Ningun kit cabe en tu presupuesto de ${presupuesto:,}. "
                    f"Este es el mas barato que puedo armar."
                )
                elegido = mas_barato.perfil

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
    """Los tres perfiles, con uno marcado. El punto de entrada de la etapa.

    Calcula UN frente de Pareto y proyecta cada perfil sobre el —los tres kits
    son tres puntos del mismo frente, comparables entre si—. Si el frente esta
    vacio (nada que optimizar) cae a la heuristica, que da el mismo kit. La
    `semilla` hace el NSGA-II reproducible: los scripts no pueden llamar al RNG
    en import, asi que se inyecta por parametro.
    """
    preferencias = preferencias or {}
    frente = optimizar_frente(renglones, preferencias, semilla=semilla)

    # Mapa sku -> Candidato por linea, para reconstruir la eleccion del frente.
    por_linea: dict[tuple[str, int], dict[str, Candidato]] = {}
    for renglon in renglones:
        if not renglon.informativa:
            por_linea[(renglon.hijo, renglon.orden)] = {c.sku: c for c in renglon.candidatos}

    kits: list[KitArmado] = []
    for perfil in PerfilKit:
        elecciones: dict[tuple[str, int], Candidato] | None = None
        punto = _proyectar(frente, perfil.value) if frente else None
        if punto is not None:
            elecciones = {
                clave: por_linea[clave][sku]
                for clave, sku in punto.asignacion.items()
                if clave in por_linea and sku in por_linea[clave]
            }
        kits.append(armar_kit(renglones, perfil.value, preferencias, elecciones=elecciones))

    return recomendar(kits, preferencias)


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
