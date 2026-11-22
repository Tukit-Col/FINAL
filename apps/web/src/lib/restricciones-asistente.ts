export const CLAVE_RESTRICCIONES = "tukit:asistente-restricciones";

export type PrioridadFormulario = "precio" | "equilibrio" | "calidad";

const PRIORIDADES: readonly PrioridadFormulario[] = ["precio", "equilibrio", "calidad"];

export interface CambiosDelAsistente {
  personajes: string | null;
  prioridad: PrioridadFormulario | null;
  presupuesto: string;
  marcasExcluidas: string[];
  soloDisponibles: boolean;
}

const MAX_MARCAS = 10;
const MAX_LARGO_MARCA = 40;

export function cambiosDelAsistente(crudo: unknown): CambiosDelAsistente | null {
  if (!crudo || typeof crudo !== "object") return null;
  const p = crudo as Record<string, unknown>;

  const personajes = Array.isArray(p.personajes)
    ? [
        ...new Set(
          p.personajes
            .filter((x): x is string => typeof x === "string")
            .map((x) => x.trim())
            .filter(Boolean),
        ),
      ]
    : [];

  const tope =
    typeof p.presupuesto_por_hijo === "number" &&
    Number.isFinite(p.presupuesto_por_hijo) &&
    p.presupuesto_por_hijo > 0
      ? Math.round(p.presupuesto_por_hijo)
      : null;

  let prioridad = PRIORIDADES.includes(p.prioridad as PrioridadFormulario)
    ? (p.prioridad as PrioridadFormulario)
    : null;
  if (tope !== null) prioridad = "equilibrio";

  const marcasExcluidas = Array.isArray(p.marcas_excluidas)
    ? [
        ...new Set(
          p.marcas_excluidas
            .filter((x): x is string => typeof x === "string")
            .map((x) => x.trim())
            .filter((x) => x.length > 0 && x.length <= MAX_LARGO_MARCA),
        ),
      ].slice(0, MAX_MARCAS)
    : [];
  const soloDisponibles = p.solo_disponibles === true;

  if (
    personajes.length === 0 &&
    prioridad === null &&
    tope === null &&
    marcasExcluidas.length === 0 &&
    !soloDisponibles
  ) {
    return null;
  }
  return {
    personajes: personajes.length > 0 ? personajes.join(", ") : null,
    prioridad,
    presupuesto: tope !== null ? String(tope) : "",
    marcasExcluidas,
    soloDisponibles,
  };
}

export function aplicarPersonajes<H extends { personajes: string }>(
  hijos: readonly H[],
  personajes: string | null,
): H[] {
  if (!personajes) return [...hijos];
  return hijos.map((h) => (h.personajes.trim() ? h : { ...h, personajes }));
}

export function leerRestriccionesGuardadas(almacen: Pick<Storage, "getItem"> | undefined): unknown {
  try {
    const texto = almacen?.getItem(CLAVE_RESTRICCIONES);
    return texto ? JSON.parse(texto) : null;
  } catch {
    return null;
  }
}

export function filtrosDePreferencias(
  marcasExcluidas: readonly string[],
  soloDisponibles: boolean,
): { marcas_excluidas?: string[]; solo_disponibles?: true } {
  return {
    ...(marcasExcluidas.length > 0 ? { marcas_excluidas: [...marcasExcluidas] } : {}),
    ...(soloDisponibles ? { solo_disponibles: true as const } : {}),
  };
}
