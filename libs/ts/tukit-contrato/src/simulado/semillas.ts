// Las semillas del origen simulado.
//
// No son datos inventados: los produce
// `herramientas/generar_semillas.py` a partir de `datos/catalogo/*.csv` (los
// mismos 99 conceptos, 242 productos y 3 tiendas que carga la base) y de
// `Arquitectura/Corpus_ItemLista_v2.csv` (las 4.719 lineas de lista de los 17
// colegios del corpus).
//
// Que sean los mismos datos es lo que hace util a la bandera: lo que la
// usuaria ve hoy con `TUKIT_ORIGEN_DATOS=simulado` es lo que el backend
// deberia devolver manana, y una diferencia entre los dos es un defecto
// visible en vez de una sorpresa el dia del cambio.

import crudoCatalogo from "./semilla-catalogo.json";
import crudoListas from "./semilla-listas.json";
import type { Catalogo, Colegio, ConceptoCatalogo, ListaOficial } from "../catalogo";

export const CATALOGO = crudoCatalogo as unknown as Catalogo;

const LISTAS = crudoListas as unknown as { colegios: Colegio[]; listas: ListaOficial[] };

export const COLEGIOS = LISTAS.colegios;

const POR_COLEGIO_GRADO = new Map<string, ListaOficial>(
  LISTAS.listas.map((l) => [`${l.colegio_id}|${l.grado}`, l]),
);

export function listaDe(colegioId: string, grado: string): ListaOficial | undefined {
  return POR_COLEGIO_GRADO.get(`${colegioId}|${grado}`);
}

export function todasLasListas(): ListaOficial[] {
  return LISTAS.listas;
}

// ------------------------------------------------------------ Normalizacion
//
// La misma idea que `concepto.sinonimos` resuelve en la base: el corpus llama
// `esfero` a lo que otra lista llama `boligrafo`. Aqui solo se necesita la
// mitad barata —bajar a minusculas, quitar tildes y colapsar espacios—
// porque los sinonimos del CSV ya vienen normalizados por el cargador.
export function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const INDICE_EXACTO = new Map<string, ConceptoCatalogo>();
for (const concepto of CATALOGO.conceptos) {
  for (const clave of [concepto.nombre_canonico, ...concepto.sinonimos]) {
    const normalizada = normalizar(clave);
    if (normalizada && !INDICE_EXACTO.has(normalizada)) INDICE_EXACTO.set(normalizada, concepto);
  }
}

const VACIAS = new Set([
  "de",
  "del",
  "la",
  "el",
  "los",
  "las",
  "un",
  "una",
  "y",
  "con",
  "para",
  "por",
  "en",
  "x",
]);

function fichas(texto: string): string[] {
  return normalizar(texto)
    .split(" ")
    .filter((t) => t.length > 2 && !VACIAS.has(t));
}

const INDICE_FICHAS = CATALOGO.conceptos.map((concepto) => ({
  concepto,
  fichas: new Set(
    [concepto.nombre_canonico, ...concepto.sinonimos].flatMap((s) => fichas(s)),
  ),
}));

/**
 * Que concepto pide un renglon de lista. Devuelve tambien la confianza, que
 * es lo que separa `RESUELTO_AUTO` de `AMBIGUO` aguas arriba.
 *
 * Primero exacto contra los sinonimos, que es el camino que resuelve la
 * mayoria, y solo si falla se paga el solapamiento de fichas. El orden
 * importa: el solapamiento sobre 99 conceptos por cada uno de los 55 renglones
 * de una lista es el costo dominante de armar el kit simulado.
 */
export function resolverConcepto(texto: string): {
  concepto: ConceptoCatalogo | null;
  confianza: number;
} {
  const exacto = INDICE_EXACTO.get(normalizar(texto));
  if (exacto) return { concepto: exacto, confianza: 0.97 };

  const buscadas = new Set(fichas(texto));
  if (buscadas.size === 0) return { concepto: null, confianza: 0 };

  let mejor: ConceptoCatalogo | null = null;
  let mejorPuntaje = 0;
  for (const entrada of INDICE_FICHAS) {
    let comunes = 0;
    for (const ficha of buscadas) if (entrada.fichas.has(ficha)) comunes += 1;
    if (comunes === 0) continue;
    const puntaje = comunes / buscadas.size;
    if (puntaje > mejorPuntaje) {
      mejorPuntaje = puntaje;
      mejor = entrada.concepto;
    }
  }

  // Por debajo de esto no hay candidato admisible: es `SIN_MATCH`, no un
  // emparejamiento flojo. Ofrecer origami cuando piden un block carta con
  // confianza es justo el defecto que el contrato separa en dos estados.
  if (mejorPuntaje < 0.34) return { concepto: null, confianza: mejorPuntaje };
  return { concepto: mejor, confianza: Math.min(0.94, 0.45 + mejorPuntaje * 0.5) };
}
