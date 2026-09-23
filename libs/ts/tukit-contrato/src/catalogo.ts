// Superficie de LECTURA del catalogo. ASUMIDA, no transcrita.
//
// A la hora de escribir esto, `arquitectura/CONTRATO_API.md` estaba en 1.0 y
// no traia la seccion de catalogo: el equipo de backend la iba a agregar como
// 1.1. Todo este fichero es una inferencia a partir de dos fuentes que si
// existen y que el backend tampoco puede contradecir sin migrar la base:
//
//   - `servicios/catalogo/tukit_catalogo/modelos/` (concepto, producto
//     canonico, oferta de tienda, precio con vigencia, lista oficial),
//   - `servicios/catalogo/tukit_catalogo/vista.py`, que ya resuelve esta
//     misma pregunta contra la base y en cuya consulta se ve que campos
//     acompanan a un producto cuando se lo muestra a una persona.
//
// Vive en su propio fichero, y no mezclado con `contrato.ts`, justamente para
// que la diferencia entre "lo que el contrato dice" y "lo que supusimos" se
// pueda ver de un vistazo cuando salga la 1.1.

import type { Dinero, ModoAdquisicion, Nivel, TipoItem, UnidadBase } from "./contrato";

export const VERSION_CATALOGO_ASUMIDA = "1.1-asumida";

export interface TiendaCatalogo {
  slug: string;
  nombre: string;
  tipo: "minorista" | "mayorista" | "editorial" | "propia";
  url_base: string | null;
}

// `precio` y `disponible` admiten nulo con significados DISTINTOS y ninguno de
// los dos es cero ni falso: `precio: null` es "no se conoce el precio" (§1.4) y
// `disponible: null` es "no se observo el stock", que es el caso normal del
// canal mayorista segun `oferta.py`.
export interface OfertaCatalogo {
  tienda: string;
  tienda_nombre: string;
  precio: Dinero | null;
  url: string | null;
  disponible: boolean | null;
  visto_en: string | null;
  confianza_vinculacion: number;
}

export interface ProductoCatalogo {
  sku: string;
  ean: string | null;
  nombre: string;
  descripcion: string | null;
  marca: string | null;
  // `nivel` y `personaje` son ejes ORTOGONALES: un cuaderno de Spiderman
  // tambien tiene nivel de calidad. La restriccion de la base lo impone y la
  // pantalla lo tiene que reflejar, no fundirlos en una sola etiqueta.
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  atributos: Record<string, unknown>;
  quality_score: number;
  es_propio: boolean;
  ofertas: OfertaCatalogo[];
}

// El detalle de un producto tal como lo sirve `_producto_publico` del backend:
// es un `ProductoCatalogo` MAS los campos que solo aparecen cuando se pide un
// producto puntual (o la busqueda paginada), no cuando cuelga de un concepto en
// el catalogo de una pieza. La SPA de admin (P4c) los necesita para el
// formulario de edicion: unidad y empaque para el precio por unidad, el concepto
// para poder reclasificar, y `precio_desde`/`tiendas` para el encabezado.
//
// PATCH y reclasificar responden con esta forma (el producto ya actualizado).
export interface ProductoCatalogoDetalle extends ProductoCatalogo {
  unidad_base: UnidadBase;
  unidades_por_empaque: number;
  concepto: { codigo: string; nombre: string };
  precio_desde: Dinero | null;
  tiendas: number;
}

// Los campos que el revisor puede reescribir en un producto (cuerpo del PATCH).
// Todos opcionales: se manda solo lo que cambio. `personaje` admite `null` para
// desligar un producto de su franquicia; `atributos` reemplaza el mapa entero.
export interface ProductoEditable {
  nombre?: string;
  descripcion?: string | null;
  marca?: string | null;
  nivel?: Nivel;
  personaje?: string | null;
  imagen_url?: string | null;
  unidad_base?: UnidadBase;
  unidades_por_empaque?: number;
  atributos?: Record<string, unknown>;
  quality_score?: number;
  es_propio?: boolean;
}

// El cuerpo de la reclasificacion: mover un producto bajo otro concepto.
export interface ReclasificarProducto {
  concepto: string;
}

// Los filtros del buscador de productos (`GET /v1/catalogo/productos`), tal como
// la SPA los pinta. Todos opcionales: sin filtros trae la primera pagina.
export interface FiltrosProductos {
  concepto?: string;
  nivel?: Nivel;
  personaje?: string;
  con_personaje?: boolean;
  busqueda?: string;
  con_precio?: boolean;
  con_ofertas?: boolean;
  pagina?: number;
  por_pagina?: number;
}

// El sobre paginado que devuelve la busqueda de productos. Los items ya vienen
// en la forma de detalle (`_producto_publico`), con concepto/unidad/empaque.
export interface PaginaProductos {
  total: number;
  pagina: number;
  por_pagina: number;
  productos: ProductoCatalogoDetalle[];
}

// Un personaje del catalogo, con cuantos productos lo llevan y —opcional— bajo
// que conceptos aparece. Lo consume el catalogo de personajes de la SPA (P4c) y
// el refactor de `empezar` (P4b).
export interface Personaje {
  nombre: string;
  productos: number;
  conceptos?: string[];
}

export interface ConceptoCatalogo {
  codigo: string;
  nombre_canonico: string;
  sinonimos: string[];
  categoria: string;
  tipo_item: TipoItem;
  // `discriminantes` filtra candidatos; `descriptivos` solo se le muestra al
  // acudiente. Que un atributo este en las dos listas es imposible por
  // restriccion de la base.
  atributos_discriminantes: string[];
  atributos_descriptivos: string[];
  admite_personaje: boolean;
  frecuencia_demanda: number;
  productos: ProductoCatalogo[];
}

export interface ResumenCatalogo {
  conceptos: number;
  productos: number;
  conceptos_con_tres_niveles: number;
  conceptos_sin_producto: number;
  productos_con_foto: number;
  tiendas: number;
  productos_sin_revisar: number;
}

export interface Catalogo {
  resumen: ResumenCatalogo;
  tiendas: TiendaCatalogo[];
  conceptos: ConceptoCatalogo[];
}

// ------------------------------------------------- Colegios y listas oficiales
//
// La entrada (a) del §2 del contrato pide elegir `colegio_id` y `grado`, pero
// el documento no dice de donde sale ese catalogo de colegios. Se asume una
// lectura publica, porque sin ella esa entrada no se puede pintar.

export interface Colegio {
  colegio_id: string;
  nombre: string;
  // De que fichero del corpus salio la lista. Se expone porque el §2.2 del
  // contrato convierte la atribucion colegio-lista en un bloqueante de
  // correccion de esta ruta: el acudiente no puede detectar el error, asi que
  // lo menos que se puede hacer es mostrar contra que se esta comparando.
  fuente: string;
  atribucion_dudosa: boolean;
  // El logo del colegio aliado, tal como lo sirve identidad (`/v1/colegios`).
  // `null` cuando el colegio no cargo marca. Se lleva hasta aca para que el
  // selector pueda pintar la insignia del aliado sin una segunda lectura.
  logo_url: string | null;
  // Solo los grados con al menos una lista REVISADA (verificada). El selector
  // deriva de aqui: un colegio sin grados revisados no se puede elegir todavia.
  grados: string[];
  // Derivado de `grados.length > 0`: un colegio es "aliado" en cuanto tiene su
  // primer grado verificado. Es la misma condicion que el filtro del selector,
  // expuesta para que la pantalla no la recalcule.
  es_partner?: boolean;
}

export interface ItemListaOficial {
  orden: number;
  texto_original: string;
  texto_generico: string | null;
  cantidad: number;
  categoria: string | null;
  tipo_item: TipoItem;
  modo_adquisicion: string;
  libro?: {
    titulo: string;
    autor: string | null;
    editorial: string | null;
    periodo: string | null;
  };
}

export interface ListaOficial {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  version: number;
  items: ItemListaOficial[];
}

// ------------------------------------------------ Listas de admin (P1/P2)
//
// La entrada del indice `/v1/admin/listas` (region de trabajo del revisor):
// una version de lista importada por inteligencia, con lo que la cola necesita
// para priorizar —si ya se reviso, que numero de version es y cuantos items
// trae—. `numero` es el correlativo de version que P1 devuelve; `items` es un
// conteo, no el arreglo (ese vive en el detalle). ASUMIDO igual que el resto
// del fichero: se reconcilia con lo que P1 realmente sirve, en el borde HTTP.
export interface VersionListaAdmin {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: number;
}

// Los filtros del indice de versiones del revisor (`GET /v1/admin/listas`).
// Todos opcionales: sin filtros trae todas las versiones vigentes. `revisada`
// separa lo curado de lo pendiente; los demas acotan por colegio, grado o ano.
export interface FiltrosListasAdmin {
  revisada?: boolean;
  colegio_id?: string;
  grado?: string;
  anio_lectivo?: number;
}

// Un renglon editable de la lista, tal como el revisor lo escribe de vuelta.
// Es el cuerpo de `PATCH .../items/{item_id}` (editar) y de `POST .../items`
// (agregar) del `admin_http.py`, con todos los campos que `_valores_de_renglon`
// acepta. En una edicion todos son opcionales (se manda solo lo que cambio);
// en un alta, `texto_original` es lo unico que el backend exige. `concepto` es
// el CODIGO del concepto (C001, ...) que `_concepto_id` resuelve; `null`
// desliga el renglon y lo manda a revision (invariante del modelo). `atributos`
// reemplaza el mapa entero.
export interface ItemListaEditable {
  texto_original?: string;
  cantidad?: number;
  unidad?: UnidadBase | null;
  tipo_item?: TipoItem | null;
  modo_adquisicion?: ModoAdquisicion | null;
  concepto?: string | null;
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  atributos?: Record<string, unknown>;
  requiere_revision?: boolean;
}

// Un renglon de una version tal como lo sirve la region 3 del revisor
// (`GET /v1/admin/listas/{version_id}/revision`, `_item_publico`). El backend
// anida el concepto en `{codigo, nombre}`; aca se aplana a
// `concepto_codigo`/`concepto_nombre` (ambos `null` cuando el renglon no tiene
// concepto y va a revision) para que la tabla del revisor no desestructure en
// cada celda.
export interface ItemRevision {
  id: string;
  orden: number;
  texto_original: string;
  cantidad: number;
  unidad: UnidadBase | null;
  tipo_item: TipoItem;
  modo_adquisicion: ModoAdquisicion | null;
  instruccion_colegio: string | null;
  url_externa: string | null;
  atributos: Record<string, unknown>;
  requiere_revision: boolean;
  concepto_codigo: string | null;
  concepto_nombre: string | null;
}

// Una propuesta de producto pendiente para un renglon, tal como la sirve la
// region 4 (`propuestas` de `ver_revision`). El precio ya viene en pesos
// enteros (el backend divide `precio_centavos` entre 100) y admite `null`
// ("no se conoce el precio", §1.4). `concepto` conserva la forma cruda del
// backend: el concepto ya decidido (`{codigo, nombre}`) o el que el modelo
// sugirio sin confirmar (`{sugerido}`).
export interface PropuestaRevision {
  id: string;
  texto_origen: string;
  nombre: string;
  marca: string | null;
  imagen_url: string | null;
  precio: number | null;
  nivel_sugerido: Nivel | null;
  puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
}

// La vista completa de la region 3/4: la cabecera de la version, sus renglones
// y las propuestas pendientes. Es la forma de
// `GET /v1/admin/listas/{version_id}/revision`.
export interface RevisionLista {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: ItemRevision[];
  propuestas: PropuestaRevision[];
}

// Una sede de un colegio, tal como la sirve el detalle de identidad
// (`GET /v1/colegios/{id}`).
export interface SedeColegio {
  sede_id: string;
  nombre: string;
}

// El detalle de un colegio, mas rico que el `Colegio` del selector: trae los
// datos de identidad/marca que la pantalla de administracion edita. Es la forma
// de `GET /v1/colegios/{id}` y la respuesta de `PATCH /v1/colegios/{id}`. Los
// campos de contacto son del colegio (secretaria academica, no un menor) y
// pueden faltar (`null`).
export interface ColegioDetalle {
  colegio_id: string;
  nombre: string;
  logo_url: string | null;
  sitio_web: string | null;
  contacto_nombre: string | null;
  contacto_email: string | null;
  contacto_telefono: string | null;
  direccion: string | null;
  sedes: SedeColegio[];
}

// Los campos que el administrador puede reescribir de la identidad de un
// colegio (cuerpo del `PATCH /v1/colegios/{id}`). Todos opcionales: se manda
// solo lo que cambio. `null` limpia el campo. NO incluye `nombre` ni `sedes`:
// esos no se editan por esta ruta.
export interface ColegioEditable {
  logo_url?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
}

// Una sugerencia de lista en el backlog del administrador
// (`GET /v1/admin/sugerencias`), derivada de las `tarea_importacion` con
// origen 'sugerencia_padre'. La UNICA traza al acudiente es
// `contacto_referencia` (el usuario_id que identidad emite): NUNCA correo ni
// telefono —esa PII vive solo en identidad y no cruza aca—. `tiene_documento`
// dice si el padre adjunto evidencia sin exponer el PDF.
export interface Sugerencia {
  tarea_id: string;
  estado: string;
  colegio_id: string | null;
  grado: string | null;
  anio_lectivo: number | null;
  contacto_referencia: string | null;
  tiene_documento: boolean;
}

export const NIVELES: readonly Nivel[] = ["economico", "confiable", "premium"];

export const ETIQUETA_NIVEL: Record<Nivel, string> = {
  economico: "Economico",
  confiable: "Confiable",
  premium: "Premium",
};

export const ORDEN_NIVEL: Record<Nivel, number> = {
  economico: 0,
  confiable: 1,
  premium: 2,
};

// El precio honesto de un producto es el mas barato entre las tiendas que lo
// venden, porque es el que el kit va a pagar. Mostrar otro seria prometer de
// mas. Es la misma definicion que usa la consulta de `vista.py`.
export function precioMasBarato(producto: ProductoCatalogo): Dinero | null {
  const precios = producto.ofertas
    .map((o) => o.precio)
    .filter((p): p is number => typeof p === "number");
  return precios.length > 0 ? Math.min(...precios) : null;
}

export function unidadesDeEmpaque(producto: ProductoCatalogo): {
  unidad: UnidadBase;
  cantidad: number;
} {
  const declaradas = producto.atributos["cantidades_declaradas"];
  if (Array.isArray(declaradas)) {
    for (const token of declaradas) {
      const m = /^(\d+):unidades$/.exec(String(token));
      if (m?.[1]) return { unidad: "unidad", cantidad: Number(m[1]) };
    }
  }
  return { unidad: "unidad", cantidad: 1 };
}

export type CoberturaConcepto = "sin_productos" | "parcial" | "tres_niveles";

export function coberturaDe(concepto: ConceptoCatalogo): CoberturaConcepto {
  if (concepto.productos.length === 0) return "sin_productos";
  const niveles = new Set(concepto.productos.map((p) => p.nivel));
  return niveles.size >= 3 ? "tres_niveles" : "parcial";
}
