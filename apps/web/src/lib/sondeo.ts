import type { OrigenDatos } from "@tukit/contrato/servidor";

type ConsultaTrabajo<T> = { consultarTrabajo(trabajoId: string, token?: string): Promise<T> };

export function consultarTrabajoDelPortador<T = Awaited<ReturnType<OrigenDatos["consultarTrabajo"]>>>(
  origen: ConsultaTrabajo<T>,
  trabajoId: string,
  token: string | undefined,
): Promise<T> {
  return origen.consultarTrabajo(trabajoId, token);
}
