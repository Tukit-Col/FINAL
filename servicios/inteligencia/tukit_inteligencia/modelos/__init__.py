"""Las 12 tablas del servicio de Inteligencia, tal como las declara el manifiesto."""

from .base import (
    PESOS_POR_OMISION,
    TRANSICIONES,
    Base,
    EstadoEtapa,
    EstadoResolucion,
    EstadoTrabajo,
    PerfilKit,
    Texto,
)
from .evento import EventoProcesado
from .importacion import ImportacionLista
from .kit import Kit, LineaKit
from .resolucion import CandidatoItem, ItemCrudo, ResolucionItem, TransicionResolucion
from .trabajo import (
    ETAPAS,
    BandejaSalida,
    EtapaTrabajo,
    KitCanonico,
    TrabajoPipeline,
    puede_pasar,
)

__all__ = [
    "ETAPAS",
    "PESOS_POR_OMISION",
    "TRANSICIONES",
    "BandejaSalida",
    "Base",
    "CandidatoItem",
    "EstadoEtapa",
    "EstadoResolucion",
    "EstadoTrabajo",
    "EtapaTrabajo",
    "EventoProcesado",
    "ImportacionLista",
    "ItemCrudo",
    "Kit",
    "KitCanonico",
    "LineaKit",
    "PerfilKit",
    "ResolucionItem",
    "Texto",
    "TrabajoPipeline",
    "TransicionResolucion",
    "puede_pasar",
]
