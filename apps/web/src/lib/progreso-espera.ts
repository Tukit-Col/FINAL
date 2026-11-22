export const DURACION_PASO_MS = 1500;

export type EtapaBackend = "percepcion" | "normalizacion" | "resolucion" | "optimizacion";

export interface PasoVisible {
  clave: string;
  titulo: string;
  detalle: string;
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

export function pasosHechosPorBackend(etapas: readonly EtapaMinima[], terminado: boolean): number {
  if (terminado) return PASOS.length;
  let hechos = 0;
  for (const paso of PASOS) {
    if (paso.etapas.length === 0) break;
    const completo = paso.etapas.every((n) => etapas.some((e) => e.nombre === n && e.estado === "ok"));
    if (!completo) break;
    hechos += 1;
  }
  return hechos;
}

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
