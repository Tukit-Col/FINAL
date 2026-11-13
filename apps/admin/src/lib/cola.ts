// Logica pura de la cola de verificacion: filtros desde la URL, grupos por
// colegio, orden y paginacion. SOLO importa tipos del contrato para poder
// probarse con `node --test` sin runner de componentes.
//
// El endpoint `GET /v1/admin/listas` solo filtra por grado y anio; busqueda
// por colegio y origen se resuelven aqui, en el servidor de Next, sobre la
// respuesta ya traida.

export const POR_PAGINA = 25;

export type OrigenCola = "todos" | "acudiente" | "colegio";

export interface FiltrosCola {
  q: string;
  grado: string;
  anio: number | null;
  origen: OrigenCola;
  pagina: number;
}

/** Lo minimo que la cola lee de una version (VersionListaAdmin lo cumple). */
export interface VersionCola {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  items: number;
  tiene_contacto: boolean;
}

export interface GrupoColegio<V extends VersionCola> {
  colegio_id: string;
  nombre: string;
  versiones: V[];
  esperando: number;
  renglones: number;
}

type Params = Record<string, string | string[] | undefined>;

function uno(p: Params, k: string): string {
  const v = p[k];
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

export function leerFiltrosCola(p: Params): FiltrosCola {
  const origen = uno(p, "origen");
  const anio = Number.parseInt(uno(p, "anio"), 10);
  const pagina = Number.parseInt(uno(p, "pagina"), 10);
  return {
    q: uno(p, "q").slice(0, 80),
    grado: uno(p, "grado").slice(0, 40),
    anio: Number.isInteger(anio) && anio > 1900 && anio < 3000 ? anio : null,
    origen: origen === "acudiente" || origen === "colegio" ? origen : "todos",
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : 1,
  };
}

/** Sin tildes ni mayusculas: "Bogota" encuentra "Bogotá". */
export function normalizar(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function hayFiltros(f: FiltrosCola): boolean {
  return f.q !== "" || f.grado !== "" || f.anio !== null || f.origen !== "todos";
}

export function filtrarVersiones<V extends VersionCola>(
  versiones: readonly V[],
  f: FiltrosCola,
  nombreDe: (v: V) => string,
): V[] {
  const q = normalizar(f.q);
  return versiones.filter((v) => {
    if (f.grado && v.grado !== f.grado) return false;
    if (f.anio !== null && v.anio_lectivo !== f.anio) return false;
    if (f.origen === "acudiente" && !v.tiene_contacto) return false;
    if (f.origen === "colegio" && v.tiene_contacto) return false;
    if (q && !normalizar(`${nombreDe(v)} ${v.grado}`).includes(q)) return false;
    return true;
  });
}

/**
 * Agrupa por colegio. Orden: colegios con acudiente esperando primero (mas
 * acudientes arriba), luego por nombre. Dentro del grupo, el grado segun
 * `ordenGrado` (pedagogico).
 */
export function agruparPorColegio<V extends VersionCola>(
  versiones: readonly V[],
  nombreDe: (v: V) => string,
  ordenGrado: (a: string, b: string) => number,
): GrupoColegio<V>[] {
  const mapa = new Map<string, GrupoColegio<V>>();
  for (const v of versiones) {
    let g = mapa.get(v.colegio_id);
    if (!g) {
      g = { colegio_id: v.colegio_id, nombre: nombreDe(v), versiones: [], esperando: 0, renglones: 0 };
      mapa.set(v.colegio_id, g);
    }
    g.versiones.push(v);
    g.renglones += v.items;
    if (v.tiene_contacto) g.esperando += 1;
  }
  const grupos = [...mapa.values()];
  for (const g of grupos) {
    g.versiones.sort(
      (a, b) =>
        Number(b.tiene_contacto) - Number(a.tiene_contacto) ||
        ordenGrado(a.grado, b.grado) ||
        a.anio_lectivo - b.anio_lectivo ||
        a.version_id.localeCompare(b.version_id),
    );
  }
  return grupos.sort(
    (a, b) => b.esperando - a.esperando || a.nombre.localeCompare(b.nombre, "es"),
  );
}

export function paginar<T>(
  items: readonly T[],
  pagina: number,
  porPagina = POR_PAGINA,
): { items: T[]; pagina: number; paginas: number; total: number } {
  const paginas = Math.max(1, Math.ceil(items.length / porPagina));
  const p = Math.min(Math.max(1, pagina), paginas);
  return { items: items.slice((p - 1) * porPagina, p * porPagina), pagina: p, paginas, total: items.length };
}

/** Querystring de los filtros activos (sin valores por defecto). */
export function hrefCola(f: FiltrosCola, pagina = 1): string {
  const u = new URLSearchParams();
  if (f.q) u.set("q", f.q);
  if (f.grado) u.set("grado", f.grado);
  if (f.anio !== null) u.set("anio", String(f.anio));
  if (f.origen !== "todos") u.set("origen", f.origen);
  if (pagina > 1) u.set("pagina", String(pagina));
  const s = u.toString();
  return s ? `/cola?${s}` : "/cola";
}
