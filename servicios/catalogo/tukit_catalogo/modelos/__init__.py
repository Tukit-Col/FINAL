"""Las 19 tablas del servicio de Catalogo."""

from .base import (
    CALIDAD_POR_NIVEL,
    DIMENSION_EMBEDDING,
    UMBRAL_REVISION_MANUAL,
    Base,
    FuentePrecio,
    MetodoVinculacion,
    Nivel,
    TipoItem,
    UnidadBase,
)
from .catalogo import (
    Concepto,
    ConceptoRutaCategoria,
    GrupoVariante,
    ProductoCanonico,
    SustituibilidadConcepto,
)
from .editorial import (
    ConfiguracionColegioEditorial,
    EdicionLibro,
    PropuestaVersion,
    VersionVigente,
)
from .listas import (
    BandejaSalida,
    CorreccionLista,
    ItemListaOficial,
    ListaOficial,
    TareaImportacion,
    VersionListaOficial,
)
from .oferta import CorridaScraper, OfertaTienda, PrecioOferta, Tienda
from .propuesta import PropuestaProducto

__all__ = [
    "CorreccionLista",
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
    "PropuestaProducto",
    "ProductoCanonico",
    "PropuestaVersion",
    "SustituibilidadConcepto",
    "TareaImportacion",
    "Tienda",
    "TipoItem",
    "UnidadBase",
    "VersionListaOficial",
    "VersionVigente",
]
