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

import type { Dinero, Nivel, TipoItem, UnidadBase } from "./contrato";

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
  grados: string[];
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
