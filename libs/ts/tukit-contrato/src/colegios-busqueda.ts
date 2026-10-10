// El buscador de colegio y la regla del logo, puros y compartidos por las dos
// apps: `/empezar` (el acudiente designa el colegio de su hijo) y "Subir lista"
// de la cola del admin. Mezcla dos fuentes que quien busca no distingue: los
// colegios que Tukit ya conoce y el directorio de Bogota
// (`datos/directorio-colegios.json`, servido por cada app en
// `/directorio-colegios.json`). El directorio llega por parametro, no se importa
// aqui: asi esto corre con `node --test` y no arrastra 300 KB a quien no lo usa.

import type { Colegio } from "./catalogo";

// Una entrada del directorio de colegios de Bogota (DUEB). NO es un colegio de
// Tukit: es la guia oficial para designar un colegio aunque Tukit todavia no lo
// tenga. `imageURL` es el logo curado a mano (el DUEB no lo trae), o `null`.
export interface EntradaDirectorio {
  dane: string;
  nombre: string;
  localidad: string;
  imageURL: string | null;
}

// Lo minimo de un colegio de Tukit para buscarlo y reconducirlo por DANE.
export type ColegioBuscable = Pick<Colegio, "colegio_id" | "nombre" | "dane">;

// Desde cuantas letras se busca: con menos, el directorio devuelve medio Bogota.
export const MINIMO_BUSQUEDA = 3;

// Plegado de mayusculas y acentos: "agustiniano" encuentra "AGUSTINIANO" y
// "jose" encuentra "JOSÉ".
export function normalizarBusqueda(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

// Iniciales del colegio para el avatar cuando no hay logo: dos letras de las
// dos primeras palabras significativas, en mayuscula.
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

// DANE -> logo del directorio, solo de las entradas que tienen uno.
export function imagenesPorDane(directorio: readonly EntradaDirectorio[]): Map<string, string> {
  const imagenes = new Map<string, string>();
  for (const entrada of directorio) {
    if (entrada.imageURL) imagenes.set(entrada.dane, entrada.imageURL);
  }
  return imagenes;
}

// La regla del logo: manda el `logo_url` que el colegio cargo en Identidad;
// sin el, el `imageURL` del directorio por su DANE; sin ninguno, `null` y la UI
// pinta las iniciales.
export function logoDeColegio(
  colegio: { logo_url?: string | null; dane?: string | null },
  imagenes: ReadonlyMap<string, string>,
): string | null {
  const propio = colegio.logo_url?.trim();
  if (propio) return propio;
  return (colegio.dane && imagenes.get(colegio.dane)) || null;
}

// Los indices normalizados, una vez y no por tecla. El de colegios incluye un
// mapa por DANE —primero gana ante una colision, saltando los nulos— que es la
// clave de reconducir al colegio existente en vez de duplicarlo.
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
  // Colegios que Tukit ya conoce. `etiqueta` es compuesta ("DIRECTORIO · Tukit")
  // cuando se llego por su entrada del directorio.
  colegios: { colegio: C; etiqueta: string }[];
  // Entradas del directorio que no son de ningun colegio de Tukit.
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
  // (a) Entradas del directorio que SON un colegio de Tukit (comparten DANE).
  //     Casan por el nombre del directorio O por el nombre en Tukit, para que
  //     tanto "agustiniano" como "cacs" den con la misma fila.
  for (const { entrada, buscable } of preparada.directorio) {
    const conocido = preparada.porDane.get(entrada.dane);
    if (!conocido || vistos.has(conocido.colegio.colegio_id)) continue;
    if (buscable.includes(qn) || conocido.buscable.includes(qn)) {
      vistos.add(conocido.colegio.colegio_id);
      colegios.push({ colegio: conocido.colegio, etiqueta: `${entrada.nombre} · ${conocido.colegio.nombre}` });
    }
  }
  // (b) Colegios de Tukit que NO estan en el directorio (sin DANE, o su DANE no
  //     aparece): los que casan por su nombre, con etiqueta simple.
  for (const { colegio, buscable } of preparada.colegios) {
    if (colegio.dane && preparada.danesDirectorio.has(colegio.dane)) continue;
    if (buscable.includes(qn) && !vistos.has(colegio.colegio_id)) {
      vistos.add(colegio.colegio_id);
      colegios.push({ colegio, etiqueta: colegio.nombre });
    }
  }
  // (c) El resto del directorio, con tope.
  const directorio = preparada.directorio
    .filter(({ entrada, buscable }) => !preparada.porDane.has(entrada.dane) && buscable.includes(qn))
    .slice(0, tope)
    .map(({ entrada }) => entrada);
  return { colegios, directorio };
}
