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
    ids.length > 0 ? origen.acudientesAdmin(token, ids).catch(() => []) : Promise.resolve([]),
  ]);
  return {
    colegios: new Map(colegios.map((c) => [c.colegio_id, c.nombre])),
    correos: new Map(acudientes.map((a) => [a.usuario_id, a.correo])),
  };
}

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
