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

from .armado import (
    _armar_a_tu_medida,
    armar_los_tres,
)  # noqa: F401
from .candidatos import (
    FiltrosDuros,
    aplicar_filtros_duros,
    candidato_permitido,
    elegir_por_perfil,
    filtros_de,
)  # noqa: F401
from .frente import (
    _GENERACIONES_MAX,
    _GENERACIONES_MIN,
    _GENERACIONES_POR_DECADA,
    _POBLACION_MAX,
    _POBLACION_MIN,
    _POBLACION_POR_LINEA,
    LIMITE_ENUMERACION,
    _domina,
    _escalera_costo_marginal,
    _frente_exacto,
    _frente_nsga,
    _generaciones,
    _no_dominadas,
    _objetivos_de_asignacion,
    _poblacion,
    _poblacion_inicial,
    _proyectar,
    _solucion,
    _surtibles,
    optimizar_frente,
)  # noqa: F401
from .lineas import (
    _objetivos,
    anclar_personaje,
    armar_kit,
    consolidar,
    juntar_herramientas,
    renglones_con_personaje,
)  # noqa: F401
from .preferencias import (
    _personajes_de,
    _pesos,
    _tope,
    _tope_de_a_tu_medida,
)  # noqa: F401
from .recomendacion import (
    elegir_recomendado_maut,
    recomendar,
)  # noqa: F401
from .tipos import (
    CONCEPTOS_ANCLA,
    MODOS_SURTIBLES,
    NOTA_CONSOLIDADA,
    ORDEN_NIVEL,
    Candidato,
    KitArmado,
    LineaKit,
    Renglon,
    SolucionFrente,
    _admisibles,
    unidades_a_comprar,
)  # noqa: F401

__all__ = [
    "CONCEPTOS_ANCLA",
    "Candidato",
    "FiltrosDuros",
    "KitArmado",
    "LIMITE_ENUMERACION",
    "LineaKit",
    "MODOS_SURTIBLES",
    "NOTA_CONSOLIDADA",
    "ORDEN_NIVEL",
    "Renglon",
    "SolucionFrente",
    "_GENERACIONES_MAX",
    "_GENERACIONES_MIN",
    "_GENERACIONES_POR_DECADA",
    "_POBLACION_MAX",
    "_POBLACION_MIN",
    "_POBLACION_POR_LINEA",
    "_admisibles",
    "_armar_a_tu_medida",
    "_domina",
    "_escalera_costo_marginal",
    "_frente_exacto",
    "_frente_nsga",
    "_generaciones",
    "_no_dominadas",
    "_objetivos",
    "_objetivos_de_asignacion",
    "_personajes_de",
    "_pesos",
    "_poblacion",
    "_poblacion_inicial",
    "_proyectar",
    "_solucion",
    "_surtibles",
    "_tope",
    "_tope_de_a_tu_medida",
    "anclar_personaje",
    "aplicar_filtros_duros",
    "armar_kit",
    "armar_los_tres",
    "candidato_permitido",
    "consolidar",
    "elegir_por_perfil",
    "elegir_recomendado_maut",
    "filtros_de",
    "juntar_herramientas",
    "optimizar_frente",
    "recomendar",
    "renglones_con_personaje",
    "unidades_a_comprar",
]
