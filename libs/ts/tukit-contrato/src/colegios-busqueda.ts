import type { Colegio } from "./catalogo";

export interface EntradaDirectorio {
  dane: string;
  nombre: string;
  localidad: string;
  imageURL: string | null;
}

export type ColegioBuscable = Pick<Colegio, "colegio_id" | "nombre" | "dane">;

export const MINIMO_BUSQUEDA = 3;

export function normalizarBusqueda(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function inicialesColegio(nombre: string): string {
  const palabras = nombre
    .split(/\s+/)
    .filter((p) => p.length > 2 && !/^(de|del|la|el|los|las|y)$/i.test(p));
  const base = palabras.length > 0 ? palabras : nombre.split(/\s+/);
  return base
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

export function imagenesPorDane(directorio: readonly EntradaDirectorio[]): Map<string, string> {
  const imagenes = new Map<string, string>();
  for (const entrada of directorio) {
    if (entrada.imageURL) imagenes.set(entrada.dane, entrada.imageURL);
  }
  return imagenes;
}

export function logoDeColegio(
  colegio: { logo_url?: string | null; dane?: string | null },
  imagenes: ReadonlyMap<string, string>,
): string | null {
  return colegio.logo_url?.trim() || logoDelDirectorio(colegio, imagenes);
}

export function logoDelDirectorio(
  colegio: { logo_url?: string | null; dane?: string | null },
  imagenes: ReadonlyMap<string, string>,
): string | null {
  if (colegio.logo_url?.trim()) return null;
  return (colegio.dane && imagenes.get(colegio.dane)) || null;
}

export interface BusquedaPreparada<C extends ColegioBuscable> {
  colegios: { colegio: C; buscable: string }[];
  porDane: Map<string, { colegio: C; buscable: string }>;
  directorio: { entrada: EntradaDirectorio; buscable: string }[];
  danesDirectorio: Set<string>;
}

export function prepararBusqueda<C extends ColegioBuscable>(
  colegios: readonly C[],
  directorio: readonly EntradaDirectorio[],
): BusquedaPreparada<C> {
  const porDane = new Map<string, { colegio: C; buscable: string }>();
  const lista = colegios.map((colegio) => {
    const indexado = { colegio, buscable: normalizarBusqueda(colegio.nombre) };
    if (colegio.dane && !porDane.has(colegio.dane)) porDane.set(colegio.dane, indexado);
    return indexado;
  });
  return {
    colegios: lista,
    porDane,
    directorio: directorio.map((entrada) => ({ entrada, buscable: normalizarBusqueda(entrada.nombre) })),
    danesDirectorio: new Set(directorio.map((e) => e.dane)),
  };
}

export interface ResultadoBusquedaColegio<C extends ColegioBuscable> {
  colegios: { colegio: C; etiqueta: string }[];
  directorio: EntradaDirectorio[];
}

export function buscarColegios<C extends ColegioBuscable>(
  preparada: BusquedaPreparada<C>,
  consulta: string,
  tope = 30,
): ResultadoBusquedaColegio<C> {
  const qn = normalizarBusqueda(consulta.trim());
  if (qn.length < MINIMO_BUSQUEDA) return { colegios: [], directorio: [] };
  const colegios: { colegio: C; etiqueta: string }[] = [];
  const vistos = new Set<string>();
  for (const { entrada, buscable } of preparada.directorio) {
    const conocido = preparada.porDane.get(entrada.dane);
    if (!conocido || vistos.has(conocido.colegio.colegio_id)) continue;
    if (buscable.includes(qn) || conocido.buscable.includes(qn)) {
      vistos.add(conocido.colegio.colegio_id);
      colegios.push({ colegio: conocido.colegio, etiqueta: `${entrada.nombre} · ${conocido.colegio.nombre}` });
    }
  }
  for (const { colegio, buscable } of preparada.colegios) {
    if (colegio.dane && preparada.danesDirectorio.has(colegio.dane)) continue;
    if (buscable.includes(qn) && !vistos.has(colegio.colegio_id)) {
      vistos.add(colegio.colegio_id);
      colegios.push({ colegio, etiqueta: colegio.nombre });
    }
  }
  const directorio = preparada.directorio
    .filter(({ entrada, buscable }) => !preparada.porDane.has(entrada.dane) && buscable.includes(qn))
    .slice(0, tope)
    .map(({ entrada }) => entrada);
  return { colegios, directorio };
}
