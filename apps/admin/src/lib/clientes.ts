// La logica pura del padron de /clientes: filtros de la URL, orden y paginas.
// Sin runner de componentes: se prueba con `node --test` y solo importa tipos.
// Ningun filtro toca datos de menores (solo colegio, grado y cantidad: Ley 1581).

import type { AcudienteAdmin } from "@tukit/contrato";

export const POR_PAGINA = 25;
export const DOMINIO_PRUEBA = "@example.test";

export type OrdenClientes = "nuevo" | "antiguo";
export type CantidadHijos = "" | "0" | "1" | "2" | "3+";

export interface FiltrosClientes {
  q: string;
  colegio: string;
  grado: string;
  hijos: CantidadHijos;
  orden: OrdenClientes;
  /** `true` = ocultar las cuentas de prueba (@example.test). Por defecto visibles. */
  sinPrueba: boolean;
  pagina: number;
}

type Parametros = Record<string, string | string[] | undefined>;

function primero(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";
}

export function leerFiltrosClientes(parametros: Parametros): FiltrosClientes {
  const hijos = primero(parametros.hijos);
  const pagina = Number.parseInt(primero(parametros.pagina), 10);
  return {
    q: primero(parametros.q),
    colegio: primero(parametros.colegio),
    grado: primero(parametros.grado),
    hijos: hijos === "0" || hijos === "1" || hijos === "2" || hijos === "3+" ? hijos : "",
    orden: primero(parametros.orden) === "antiguo" ? "antiguo" : "nuevo",
    sinPrueba: primero(parametros.sinprueba) === "1",
    pagina: Number.isFinite(pagina) && pagina > 0 ? pagina : 1,
  };
}

/** Si hay algun filtro puesto (el orden y la pagina no cuentan). */
export function hayFiltrosClientes(f: FiltrosClientes): boolean {
  return Boolean(f.q || f.colegio || f.grado || f.hijos || f.sinPrueba);
}

export function esCuentaDePrueba(a: Pick<AcudienteAdmin, "correo">): boolean {
  return a.correo.toLowerCase().endsWith(DOMINIO_PRUEBA);
}

function instante(iso: string): number {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function coincideHijos(n: number, cantidad: CantidadHijos): boolean {
  if (cantidad === "") return true;
  return cantidad === "3+" ? n >= 3 : n === Number(cantidad);
}

/** Filtra y ordena por fecha de registro. No muta la entrada. */
export function filtrarClientes(
  acudientes: readonly AcudienteAdmin[],
  f: FiltrosClientes,
): AcudienteAdmin[] {
  const q = f.q.toLowerCase();
  const salida = acudientes.filter((a) => {
    if (q && !a.correo.toLowerCase().includes(q)) return false;
    if (f.sinPrueba && esCuentaDePrueba(a)) return false;
    if (!coincideHijos(a.hijos.length, f.hijos)) return false;
    if (f.colegio && !a.hijos.some((h) => h.colegio_id === f.colegio)) return false;
    if (f.grado && !a.hijos.some((h) => h.grado === f.grado)) return false;
    return true;
  });
  const signo = f.orden === "antiguo" ? 1 : -1;
  return salida.sort((a, b) => signo * (instante(a.creado_en) - instante(b.creado_en)));
}

/** Colegios y grados que existen en el padron, para los selectores. */
export function opcionesClientes(acudientes: readonly AcudienteAdmin[]): {
  colegios: { id: string; nombre: string }[];
  grados: string[];
} {
  const colegios = new Map<string, string>();
  const grados = new Set<string>();
  for (const a of acudientes) {
    for (const h of a.hijos) {
      colegios.set(h.colegio_id, h.colegio_nombre);
      grados.add(h.grado);
    }
  }
  return {
    colegios: [...colegios].map(([id, nombre]) => ({ id, nombre })).sort((x, y) => x.nombre.localeCompare(y.nombre, "es")),
    grados: [...grados].sort((x, y) => x.localeCompare(y, "es", { numeric: true })),
  };
}

export interface PaginaClientes<T> {
  items: T[];
  pagina: number;
  paginas: number;
  total: number;
  /** 1-based, para "Mostrando 26-50 de 130". 0 si no hay nada. */
  desde: number;
  hasta: number;
}

/** Recorta a una pagina; una pagina fuera de rango se lleva al limite. */
export function paginar<T>(items: readonly T[], pagina: number, tamano = POR_PAGINA): PaginaClientes<T> {
  const total = items.length;
  const paginas = Math.max(1, Math.ceil(total / tamano));
  const actual = Math.min(Math.max(1, pagina), paginas);
  const inicio = (actual - 1) * tamano;
  const parte = items.slice(inicio, inicio + tamano);
  return {
    items: parte,
    pagina: actual,
    paginas,
    total,
    desde: total === 0 ? 0 : inicio + 1,
    hasta: inicio + parte.length,
  };
}

/** El enlace a una pagina conservando los filtros. */
export function hrefClientes(f: FiltrosClientes, cambios: Partial<FiltrosClientes> = {}): string {
  const x = { ...f, ...cambios };
  const p = new URLSearchParams();
  if (x.q) p.set("q", x.q);
  if (x.colegio) p.set("colegio", x.colegio);
  if (x.grado) p.set("grado", x.grado);
  if (x.hijos) p.set("hijos", x.hijos);
  if (x.orden !== "nuevo") p.set("orden", x.orden);
  if (x.sinPrueba) p.set("sinprueba", "1");
  if (x.pagina > 1) p.set("pagina", String(x.pagina));
  const cola = p.toString();
  return cola ? `/clientes?${cola}` : "/clientes";
}

/** Un colegio del padron con cuantos acudientes e hijos tiene, en total y por grado. */
export interface ClientesDeColegio {
  colegio_id: string;
  colegio_nombre: string;
  acudientes: number;
  hijos: number;
  grados: { grado: string; acudientes: number; hijos: number }[];
}

/**
 * Cuantos clientes hay por colegio y por grado. Un acudiente cuenta UNA vez en
 * cada colegio (y en cada grado) donde tiene al menos un hijo, aunque tenga dos
 * hijos ahi; los hijos se cuentan todos. Solo colegio, grado y cantidades: ningun
 * dato del menor (Ley 1581). Colegios de mas a menos acudientes; grados por
 * cantidad de hijos y luego por nombre.
 */
export function clientesPorColegio(acudientes: readonly AcudienteAdmin[]): ClientesDeColegio[] {
  type Acum = { nombre: string; padres: Set<string>; hijos: number; grados: Map<string, { padres: Set<string>; hijos: number }> };
  const colegios = new Map<string, Acum>();
  for (const a of acudientes) {
    for (const h of a.hijos) {
      let c = colegios.get(h.colegio_id);
      if (!c) {
        c = { nombre: h.colegio_nombre, padres: new Set(), hijos: 0, grados: new Map() };
        colegios.set(h.colegio_id, c);
      }
      c.padres.add(a.usuario_id);
      c.hijos += 1;
      let g = c.grados.get(h.grado);
      if (!g) {
        g = { padres: new Set(), hijos: 0 };
        c.grados.set(h.grado, g);
      }
      g.padres.add(a.usuario_id);
      g.hijos += 1;
    }
  }
  return [...colegios.entries()]
    .map(([colegio_id, c]) => ({
      colegio_id,
      colegio_nombre: c.nombre,
      acudientes: c.padres.size,
      hijos: c.hijos,
      grados: [...c.grados.entries()]
        .map(([grado, g]) => ({ grado, acudientes: g.padres.size, hijos: g.hijos }))
        .sort((x, y) => y.hijos - x.hijos || x.grado.localeCompare(y.grado, "es")),
    }))
    .sort((x, y) => y.acudientes - x.acudientes || x.colegio_nombre.localeCompare(y.colegio_nombre, "es"));
}
