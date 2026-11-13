// Las reglas puras de la pantalla de progreso al armar el kit: cuatro pasos con
// nombre, cuál va según el backend y cuánto debe verse cada uno. Sin React ni
// reloj propios, para probarlas con `node --test`.
//
// Cortesía, no retraso: las llamadas al backend no esperan a nada. Si el
// backend termina antes, la pantalla recorre los pasos que faltan a razón de
// `DURACION_PASO_MS` cada uno (4 pasos = 6 s como tope) para que se alcance a
// leer qué pasó; si el backend tarda, la pantalla nunca va más adelante que él.

export const DURACION_PASO_MS = 1500;

export type EtapaBackend = "percepcion" | "normalizacion" | "resolucion" | "optimizacion";

export interface PasoVisible {
  clave: string;
  titulo: string;
  detalle: string;
  /** Etapas del backend que deben estar completas para dar este paso por hecho. */
  etapas: readonly EtapaBackend[];
}

export const PASOS: readonly PasoVisible[] = [
  {
    clave: "leer",
    titulo: "Leyendo tu lista",
    detalle: "Sacando renglón por renglón lo que pide el colegio.",
    etapas: ["percepcion"],
  },
  {
    clave: "buscar",
    titulo: "Buscando productos",
    detalle: "Un esfero y un bolígrafo son lo mismo; un cuaderno de 100 hojas no es cualquiera.",
    etapas: ["normalizacion", "resolucion"],
  },
  {
    clave: "armar",
    titulo: "Armando tus 3 kits",
    detalle: "Comparando precio entre tiendas y juntando lo repetido entre hermanos.",
    etapas: ["optimizacion"],
  },
  {
    clave: "revisar",
    titulo: "Última revisión",
    detalle: "Le damos una mirada final antes de mostrártelo.",
    etapas: [],
  },
];

export interface EtapaMinima {
  nombre: string;
  estado: string;
}

/** Cuántos pasos, contados desde el primero, el backend ya terminó (0 a 4). */
export function pasosHechosPorBackend(etapas: readonly EtapaMinima[], terminado: boolean): number {
  if (terminado) return PASOS.length;
  let hechos = 0;
  for (const paso of PASOS) {
    if (paso.etapas.length === 0) break; // la revisión final solo la cierra el estado
    const completo = paso.etapas.every((n) => etapas.some((e) => e.nombre === n && e.estado === "ok"));
    if (!completo) break;
    hechos += 1;
  }
  return hechos;
}

/**
 * ¿Hay que avanzar el paso que se ve? Devuelve cuántos pasos se muestran hechos
 * ahora y, si falta camino, en cuántos ms toca el siguiente movimiento.
 * `desdeCambioMs` es lo que lleva el paso actual a la vista.
 */
export function siguienteMovimiento(
  visibles: number,
  objetivo: number,
  desdeCambioMs: number,
  duracionMs: number = DURACION_PASO_MS,
): { visibles: number; enMs: number | null } {
  const tope = Math.min(objetivo, PASOS.length);
  if (visibles >= tope) return { visibles, enMs: null };
  const falta = duracionMs - desdeCambioMs;
  if (falta <= 0) return { visibles: visibles + 1, enMs: visibles + 1 < tope ? duracionMs : null };
  return { visibles, enMs: falta };
}
