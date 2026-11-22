import type { Kit, LineaKit, ProductoKit, Trabajo } from "./contrato";
import type { ConceptoCatalogo, DatosColegioNuevo, ItemListaEditable, ItemRevision, OfertaCatalogo, ProductoCatalogo, ProductoCatalogoDetalle, PropuestaRevision } from "./catalogo";

export function normalizarProducto(p: unknown): ProductoKit | null {
  if (!p || typeof p !== "object") return null;
  const crudo = p as Record<string, unknown>;
  const precio =
    typeof crudo["precio"] === "number"
      ? (crudo["precio"] as number)
      : typeof crudo["precio_cop"] === "number"
        ? (crudo["precio_cop"] as number)
        : null;

  const ofertasCrudas = crudo["ofertas"];
  const ofertas = Array.isArray(ofertasCrudas)
    ? (ofertasCrudas as ProductoKit["ofertas"])
    : precio !== null
      ? [{ tienda: "", precio, vigente_hasta: null }]
      : [];

  return {
    sku: String(crudo["sku"] ?? ""),
    nombre: String(crudo["nombre"] ?? ""),
    marca: (crudo["marca"] as string | null) ?? null,
    nivel: crudo["nivel"] as ProductoKit["nivel"],
    personaje: (crudo["personaje"] as string | null) ?? null,
    imagen_url: (crudo["imagen_url"] as string | null) ?? null,
    confianza: typeof crudo["confianza"] === "number" ? (crudo["confianza"] as number) : 1,
    ofertas,
  };
}

export function normalizarLinea(linea: LineaKit): LineaKit {
  return {
    ...linea,
    producto_elegido: normalizarProducto(linea.producto_elegido),
    alternativas: Array.isArray(linea.alternativas)
      ? linea.alternativas.map(normalizarProducto).filter((p): p is ProductoKit => p !== null)
      : [],
  };
}

export function normalizarKit(kit: Kit): Kit {
  return { ...kit, lineas: (kit.lineas ?? []).map(normalizarLinea) };
}

export function normalizarTrabajo(trabajo: Trabajo): Trabajo {
  return { ...trabajo, kits: (trabajo.kits ?? []).map(normalizarKit) };
}

export interface ConceptoCrudo {
  codigo: string;
  nombre_canonico?: string;
  nombre?: string;
  sinonimos?: string[];
  categoria: string;
  tipo_item: ConceptoCatalogo["tipo_item"];
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
  admite_personaje?: boolean;
  frecuencia_demanda?: number;
}

export interface ProductoCrudo {
  sku: string;
  ean?: string | null;
  nombre: string;
  descripcion?: string | null;
  marca?: string | null;
  nivel: ProductoCatalogo["nivel"];
  personaje?: string | null;
  imagen_url?: string | null;
  atributos?: Record<string, unknown>;
  quality_score?: number;
  es_propio?: boolean;
  concepto?: { codigo: string; nombre: string } | null;
  ofertas?: OfertaCatalogo[];
  unidad_base?: ProductoCatalogoDetalle["unidad_base"];
  unidades_por_empaque?: number;
  precio_desde?: number | null;
  tiendas?: number;
}

export interface PersonajeCrudo {
  nombre: string;
  productos?: number;
  conceptos?: string[];
}

export function normalizarProductoCatalogo(p: ProductoCrudo): ProductoCatalogo {
  return {
    sku: p.sku,
    ean: p.ean ?? null,
    nombre: p.nombre,
    descripcion: p.descripcion ?? null,
    marca: p.marca ?? null,
    nivel: p.nivel,
    personaje: p.personaje ?? null,
    imagen_url: p.imagen_url ?? null,
    atributos: p.atributos ?? {},
    quality_score: typeof p.quality_score === "number" ? p.quality_score : 0,
    es_propio: Boolean(p.es_propio),
    ofertas: Array.isArray(p.ofertas) ? p.ofertas : [],
  };
}

export function normalizarProductoDetalle(p: ProductoCrudo): ProductoCatalogoDetalle {
  const base = normalizarProductoCatalogo(p);
  const ofertados = base.ofertas
    .map((o) => o.precio)
    .filter((x): x is number => typeof x === "number");
  const precioDesde =
    typeof p.precio_desde === "number"
      ? p.precio_desde
      : ofertados.length > 0
        ? Math.min(...ofertados)
        : null;
  return {
    ...base,
    unidad_base: p.unidad_base ?? "unidad",
    unidades_por_empaque:
      typeof p.unidades_por_empaque === "number" ? p.unidades_por_empaque : 1,
    concepto: p.concepto ?? { codigo: "", nombre: "" },
    precio_desde: precioDesde,
    tiendas: typeof p.tiendas === "number" ? p.tiendas : base.ofertas.length,
  };
}

export interface ItemRevisionCrudo {
  item_id: string;
  orden: number;
  texto_original: string;
  cantidad: number;
  unidad?: ItemRevision["unidad"];
  tipo_item: ItemRevision["tipo_item"];
  modo_adquisicion?: ItemRevision["modo_adquisicion"];
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  atributos?: Record<string, unknown>;
  requiere_revision?: boolean;
  concepto?: { codigo: string; nombre: string } | null;
  atributos_discriminantes?: string[];
  atributos_leidos?: Record<string, unknown>;
  atributos_exigidos?: Record<string, unknown>;
  atributos_por_revisar?: string[];
  atributos_deducidos?: string[];
}

export interface PropuestaRevisionCruda {
  id: string;
  texto_origen: string;
  item_id?: string | null;
  nombre: string;
  marca?: string | null;
  imagen_url?: string | null;
  precio?: number | null;
  nivel_sugerido?: PropuestaRevision["nivel_sugerido"];
  puntaje?: number;
  concepto?: { codigo: string; nombre: string } | { sugerido: string | null };
}

export interface RevisionCruda {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada?: boolean;
  items?: ItemRevisionCrudo[];
  propuestas?: PropuestaRevisionCruda[];
  colegio_datos?: DatosColegioNuevo | null;
}

export interface ColegioDetalleCrudo {
  colegio_id: string;
  nombre: string;
  dane?: string | null;
  logo_url?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
  direccion?: string | null;
  sedes?: { sede_id: string; nombre: string }[];
}

export interface SugerenciaCruda {
  tarea_id: string;
  estado: string;
  colegio_id?: string | null;
  grado?: string | null;
  anio_lectivo?: number | null;
  contacto_referencia?: string | null;
  tiene_documento?: boolean;
}

export function normalizarItemRevision(i: ItemRevisionCrudo): ItemRevision {
  return {
    id: i.item_id,
    orden: i.orden,
    texto_original: i.texto_original,
    cantidad: i.cantidad,
    unidad: i.unidad ?? null,
    tipo_item: i.tipo_item,
    modo_adquisicion: i.modo_adquisicion ?? null,
    instruccion_colegio: i.instruccion_colegio ?? null,
    url_externa: i.url_externa ?? null,
    atributos: i.atributos ?? {},
    requiere_revision: Boolean(i.requiere_revision),
    concepto_codigo: i.concepto?.codigo ?? null,
    concepto_nombre: i.concepto?.nombre ?? null,
    atributos_discriminantes: i.atributos_discriminantes ?? [],
    atributos_leidos: i.atributos_leidos ?? {},
    atributos_exigidos: i.atributos_exigidos ?? {},
    atributos_por_revisar: i.atributos_por_revisar ?? [],
    atributos_deducidos: i.atributos_deducidos ?? [],
  };
}

export function normalizarPropuestaRevision(p: PropuestaRevisionCruda): PropuestaRevision {
  return {
    id: p.id,
    texto_origen: p.texto_origen,
    item_id: p.item_id ?? null,
    nombre: p.nombre,
    marca: p.marca ?? null,
    imagen_url: p.imagen_url ?? null,
    precio: typeof p.precio === "number" ? p.precio : null,
    nivel_sugerido: p.nivel_sugerido ?? null,
    puntaje: typeof p.puntaje === "number" ? p.puntaje : 0,
    concepto: p.concepto ?? { sugerido: null },
  };
}

export function cuerpoItem(item: ItemListaEditable): Record<string, unknown> {
  const cuerpo: Record<string, unknown> = {
    texto_original: item.texto_original,
    cantidad: item.cantidad,
    unidad: item.unidad,
    tipo_item: item.tipo_item,
    modo_adquisicion: item.modo_adquisicion,
    instruccion_colegio: item.instruccion_colegio,
    url_externa: item.url_externa,
    atributos: item.atributos,
    requiere_revision: item.requiere_revision,
  };
  if ("concepto" in item) cuerpo["concepto_codigo"] = item.concepto;
  return cuerpo;
}
