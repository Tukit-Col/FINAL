import type { Dinero, ModoAdquisicion, Nivel, TipoItem, UnidadBase } from "./contrato";

export const VERSION_CATALOGO_ASUMIDA = "1.1-asumida";

export interface TiendaCatalogo {
  slug: string;
  nombre: string;
  tipo: "minorista" | "mayorista" | "editorial" | "propia";
  url_base: string | null;
}

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
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  atributos: Record<string, unknown>;
  quality_score: number;
  es_propio: boolean;
  ofertas: OfertaCatalogo[];
}

export interface ProductoCatalogoDetalle extends ProductoCatalogo {
  unidad_base: UnidadBase;
  unidades_por_empaque: number;
  concepto: { codigo: string; nombre: string };
  precio_desde: Dinero | null;
  tiendas: number;
}

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

export interface ReclasificarProducto {
  concepto: string;
}

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

export interface PaginaProductos {
  total: number;
  pagina: number;
  por_pagina: number;
  productos: ProductoCatalogoDetalle[];
}

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

export interface Colegio {
  colegio_id: string;
  nombre: string;
  dane: string | null;
  fuente: string;
  atribucion_dudosa: boolean;
  logo_url: string | null;
  grados: string[];
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

interface AvisoBase {
  item_id: string;
  orden: number;
  texto: string;
  concepto_codigo: string | null;
  concepto_nombre: string | null;
  clave: string;
}

export type AvisoLista =
  | (AvisoBase & { tipo: "posible_repetido"; repite_a: number; texto_repetido: string | null })
  | (AvisoBase & { tipo: "revisar_atributo"; atributo: string })
  | (AvisoBase & { tipo: "sin_producto"; exige: Record<string, unknown> });

export interface ListaOficial {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  version: number;
  version_id?: string;
  items: ItemListaOficial[];
}

export interface VersionListaAdmin {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: number;
  procedencia: ProcedenciaVersion | null;
  tiene_contacto: boolean;
  colegio_nombre: string | null;
}

export type ProcedenciaVersion = "onboarding" | "sugerencia_padre";

export interface FiltrosListasAdmin {
  revisada?: boolean;
  colegio_id?: string;
  grado?: string;
  anio_lectivo?: number;
}

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
  atributos_discriminantes: string[];
  atributos_leidos: Record<string, unknown>;
  atributos_exigidos: Record<string, unknown>;
  atributos_por_revisar: string[];
  atributos_deducidos: string[];
}

export interface PropuestaRevision {
  id: string;
  texto_origen: string;
  item_id: string | null;
  nombre: string;
  marca: string | null;
  imagen_url: string | null;
  precio: number | null;
  nivel_sugerido: Nivel | null;
  puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
}

export interface PropuestaCola {
  id: string;
  id_corto: string;
  texto_origen: string;
  nombre: string;
  marca: string | null;
  imagen_url: string | null;
  precio: number | null;
  nivel_sugerido: string | null;
  puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
  origen: string;
  atributos_verificados?: Record<string, unknown>;
  atributos_al_aprobar?: Record<string, unknown>;
}

export interface CandidatoTienda {
  slug: string;
  sku: string;
  nombre: string;
  precio: number;
  marca: string | null;
  ean: string | null;
  url: string;
  imagen_url: string | null;
  disponible: boolean;
  especificaciones: Record<string, string>;
}

export interface AltaUtil {
  concepto: string;
  slug: string;
  sku: string;
  consulta: string;
  nivel: string;
}

export interface CrearConcepto {
  nombre_canonico: string;
  categoria: string;
  sinonimos?: string;
  tipo_item?: string;
  admite_personaje?: boolean;
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
}

export interface ConceptoCreado {
  codigo: string;
  nombre_canonico: string;
  categoria: string;
  tipo_item: string;
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
}

export interface AltaUtilManual {
  concepto: string;
  nombre: string;
  precio: number;
  slug: string;
  sku?: string;
  url?: string;
  marca?: string;
  nivel: string;
}

export interface AltaLibro {
  concepto: string;
  isbn: string;
  titulo: string;
  precio: number;
  slug: string;
  nivel: string;
}

export interface AprobarPropuesta {
  nivel: string;
  nombre?: string;
  marca?: string | null;
  imagen_url?: string | null;
  personaje?: string | null;
  atributos?: Record<string, string | number | boolean>;
}

export interface RechazarPropuesta {
  motivo?: string;
  no_surtir?: boolean;
}

export interface PropuestaEncolada {
  id: string;
  id_corto: string;
  estado: string;
}

export interface RevisionLista {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: ItemRevision[];
  propuestas: PropuestaRevision[];
  colegio_datos: DatosColegioNuevo | null;
}

export interface DatosColegioNuevo {
  nombre?: string | null;
  dane?: string | null;
  logo_url?: string | null;
  sitio_web?: string | null;
  direccion?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
}

export interface ColegioNuevoEditable {
  nombre?: string;
  logo_url?: string;
  sitio_web?: string;
  direccion?: string;
  contacto_nombre?: string;
  contacto_email?: string;
  contacto_telefono?: string;
}

export interface SedeColegio {
  sede_id: string;
  nombre: string;
}

export interface ColegioDetalle {
  colegio_id: string;
  nombre: string;
  dane: string | null;
  logo_url: string | null;
  sitio_web: string | null;
  contacto_nombre: string | null;
  contacto_email: string | null;
  contacto_telefono: string | null;
  direccion: string | null;
  sedes: SedeColegio[];
}

export interface ColegioEditable {
  dane?: string | null;
  logo_url?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
}

export type ColegioDesignado =
  | { colegio_id: string }
  | { colegio_dane: string; colegio_nombre: string }
  | { colegio_nombre: string };

export interface DirectorioColegio {
  dane?: string | null;
  nombre?: string | null;
  direccion?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
  sector?: string | null;
  localidad?: string | null;
  rector?: string | null;
  telefonos?: string[];
  correos?: string[];
}

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

export function inferirTipoAtributo(texto: string): string | number | boolean {
  const limpio = texto.trim();
  if (limpio === "true") return true;
  if (limpio === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(limpio)) {
    const n = Number(limpio);
    if (Number.isFinite(n) && String(n) === limpio) return n;
  }
  return texto;
}

export function serializarAtributos(
  pares: { clave: string; valor: string }[],
): Record<string, string | number | boolean> {
  const salida: Record<string, string | number | boolean> = {};
  for (const { clave, valor } of pares) {
    const k = clave.trim();
    if (!k || valor === "") continue;
    salida[k] = inferirTipoAtributo(valor);
  }
  return salida;
}
