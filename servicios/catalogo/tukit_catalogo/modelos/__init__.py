"""Las 17 tablas del servicio de Catalogo."""

from .base import (
    CALIDAD_POR_NIVEL,
    DIMENSION_EMBEDDING,
    UMBRAL_REVISION_MANUAL,
    Base,
    FuentePrecio,
    MetodoVinculacion,
    Nivel,
)
from .catalogo import Concepto, ConceptoRutaCategoria, GrupoVariante, ProductoCanonico
from .editorial import (
    ConfiguracionColegioEditorial,
    EdicionLibro,
    PropuestaVersion,
    VersionVigente,
)
from .listas import (
    BandejaSalida,
    ItemListaOficial,
    ListaOficial,
    TareaImportacion,
    VersionListaOficial,
)
from .oferta import CorridaScraper, OfertaTienda, PrecioOferta, Tienda

__all__ = [
    "CALIDAD_POR_NIVEL",
    "DIMENSION_EMBEDDING",
    "UMBRAL_REVISION_MANUAL",
    "Base",
    "BandejaSalida",
    "Concepto",
    "ConceptoRutaCategoria",
    "ConfiguracionColegioEditorial",
    "CorridaScraper",
    "EdicionLibro",
    "FuentePrecio",
    "GrupoVariante",
    "ItemListaOficial",
    "ListaOficial",
    "MetodoVinculacion",
    "Nivel",
    "OfertaTienda",
    "PrecioOferta",
    "ProductoCanonico",
    "PropuestaVersion",
    "TareaImportacion",
    "Tienda",
    "VersionListaOficial",
    "VersionVigente",
]
