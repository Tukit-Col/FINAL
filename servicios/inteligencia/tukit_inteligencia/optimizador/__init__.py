"""Los tres kits sobre un frente de Pareto NSGA-II.

Decisiones:
- Se calcula un solo frente de Pareto y cada kit es una proyeccion suya, asi que son comparables
  entre si. Si no hay compromiso que optimizar (ninguna linea decidible o todas con un candidato)
  se cae a la heuristica, que da el mismo kit.
- pymoo es dependencia dura: si falta, el servicio no arranca. Degradar en silencio serviria kits
  que no son los del algoritmo.
- `elegir_por_perfil` queda para la linea de un unico candidato y como referencia de la prueba de
  hipervolumen; nunca es el plan B de una falta de pymoo.
- Los filtros duros del acudiente (marcas excluidas, solo disponibles) se aplican a los candidatos
  antes del frente, no como un peso. El presupuesto es una cota que se aplica despues del frente:
  un frente recortado esconderia opciones validas.
- `unidades_a_comprar` es techo(cantidad pedida / unidades por empaque) y el total incluye solo lo
  que Tukit puede entregar: una linea informativa se muestra y no se cobra.
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
