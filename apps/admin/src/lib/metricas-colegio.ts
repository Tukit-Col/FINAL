import type { Sugerencia } from "@tukit/contrato";

export interface DemandaGrado {
  grado: string;
  solicitudes: number;
}

export function demandaPorGrado(
  sugerencias: Sugerencia[],
  colegioId: string,
  gradosVerificados: ReadonlySet<string>,
): DemandaGrado[] {
  const conteo = new Map<string, number>();
  for (const s of sugerencias) {
    if (s.colegio_id !== colegioId) continue;
    if (s.contacto_referencia === null) continue;
    if (!s.grado) continue;
    if (gradosVerificados.has(s.grado)) continue;
    conteo.set(s.grado, (conteo.get(s.grado) ?? 0) + 1);
  }
  return [...conteo.entries()]
    .map(([grado, solicitudes]) => ({ grado, solicitudes }))
    .sort((a, b) => b.solicitudes - a.solicitudes || a.grado.localeCompare(b.grado));
}
