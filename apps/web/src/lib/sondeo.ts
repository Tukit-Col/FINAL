// La consulta del sondeo de `/esperando`, separada de la ruta para poder
// probarla sin servidor.
//
// Viaja con el token de la cookie, como las demas rutas de la web: sin el, el
// gateway solo la cuenta por IP y el limite por cuenta (ADR 0047) nunca la
// frena, asi que la pantalla de espera no podia mostrar su aviso. Sin cookie
// (la ruta rapida admite trabajos anonimos) va sin token, igual que antes:
// `GET /v1/trabajos/{id}` no lo exige.

import type { OrigenDatos } from "@tukit/contrato/servidor";

type ConsultaTrabajo<T> = { consultarTrabajo(trabajoId: string, token?: string): Promise<T> };

export function consultarTrabajoDelPortador<T = Awaited<ReturnType<OrigenDatos["consultarTrabajo"]>>>(
  origen: ConsultaTrabajo<T>,
  trabajoId: string,
  token: string | undefined,
): Promise<T> {
  return origen.consultarTrabajo(trabajoId, token);
}
