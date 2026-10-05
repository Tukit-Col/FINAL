// Lo que Logística muestra en palabras y comercio guarda como ids: el nombre de
// cada colegio y el correo de cada acudiente. Vive aparte de `logistica.ts`
// porque ese modulo lo usa tambien un componente de cliente y esto lee del
// origen de servidor. Es un adorno: si identidad no responde, la pagina sigue
// con los ids en vez de caerse.

import type { Pedido } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";

export interface EtiquetasLogistica {
  colegios: Map<string, string>;
  correos: Map<string, string>;
}

export async function etiquetasDePedidos(
  token: string,
  pedidos: readonly Pedido[],
): Promise<EtiquetasLogistica> {
  const origen = origenDeDatos();
  const ids = [...new Set(pedidos.map((p) => p.usuario_id))];
  const [colegios, acudientes] = await Promise.all([
    origen.colegios().catch(() => []),
    // El padron de identidad es solo para staff y no incluye cuentas internas
    // ni contactos invitados: esos quedan sin correo.
    ids.length > 0 ? origen.acudientesAdmin(token, ids).catch(() => []) : Promise.resolve([]),
  ]);
  return {
    colegios: new Map(colegios.map((c) => [c.colegio_id, c.nombre])),
    correos: new Map(acudientes.map((a) => [a.usuario_id, a.correo])),
  };
}

/** Los colegios de los pedidos, con su nombre, ordenados para el filtro. */
export function opcionesDeColegio(
  pedidos: readonly Pedido[],
  nombres: ReadonlyMap<string, string>,
): { id: string; nombre: string }[] {
  const ids = [...new Set(pedidos.flatMap((p) => p.colegios))];
  return ids
    .map((id) => ({ id, nombre: nombres.get(id) ?? id }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
}

export function nombresDeColegios(ids: readonly string[], nombres: ReadonlyMap<string, string>): string {
  return ids.map((id) => nombres.get(id) ?? id).join(", ");
}
