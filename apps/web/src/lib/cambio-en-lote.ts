// Cambio de marca en lote para una categoría del kit. Reglas puras: la UI
// (CabeceraCategoria) y el asistente de la Fase 5 comparten el mismo plan.

import type { LineaKit, OpcionDeLinea } from "@tukit/contrato";
import { normalizarTexto } from "./kit-vista.ts";

export type OpcionesPorLinea = Record<string, OpcionDeLinea[]>;

export interface PlanDeCambio {
  cambian: { item_id: string; sku: string }[];
  sinEsaMarca: string[];
}

const mismaMarca = (o: OpcionDeLinea, marca: string) =>
  o.marca != null && normalizarTexto(o.marca) === normalizarTexto(marca);

/** Marcas que aparecen en alguna línea, por cobertura descendente. */
export function marcasDisponibles(opcionesPorLinea: OpcionesPorLinea): { marca: string; lineas: number }[] {
  const cuentas = new Map<string, { marca: string; lineas: number }>();
  for (const opciones of Object.values(opcionesPorLinea)) {
    const vistas = new Set<string>();
    for (const o of opciones) {
      if (!o.marca?.trim()) continue;
      const clave = normalizarTexto(o.marca);
      if (vistas.has(clave)) continue;
      vistas.add(clave);
      const previa = cuentas.get(clave);
      if (previa) previa.lineas += 1;
      else cuentas.set(clave, { marca: o.marca.trim(), lineas: 1 });
    }
  }
  return [...cuentas.values()].sort((a, b) => b.lineas - a.lineas || a.marca.localeCompare(b.marca, "es"));
}

export function planDeCambioPorMarca(
  lineas: readonly Pick<LineaKit, "item_id" | "descartado">[],
  opcionesPorLinea: OpcionesPorLinea,
  marca: string,
): PlanDeCambio {
  const plan: PlanDeCambio = { cambian: [], sinEsaMarca: [] };
  for (const linea of lineas) {
    if (linea.descartado) continue;
    const opciones = opcionesPorLinea[linea.item_id] ?? [];
    const deLaMarca = opciones.filter((o) => mismaMarca(o, marca));
    if (deLaMarca.length === 0) {
      plan.sinEsaMarca.push(linea.item_id);
      continue;
    }
    if (deLaMarca.some((o) => o.en_kit)) continue; // ya la tiene
    const barata = deLaMarca.reduce((a, b) => (b.precio < a.precio ? b : a));
    plan.cambian.push({ item_id: linea.item_id, sku: barata.sku });
  }
  return plan;
}

/** Aplica el plan una línea a la vez; un fallo no detiene las demás. */
export async function aplicarPlanEnLote(
  plan: PlanDeCambio,
  cambiar: (itemId: string, sku: string) => Promise<unknown>,
): Promise<{ hechos: number; fallidos: string[] }> {
  let hechos = 0;
  const fallidos: string[] = [];
  for (const { item_id, sku } of plan.cambian) {
    try {
      await cambiar(item_id, sku);
      hechos += 1;
    } catch {
      fallidos.push(item_id);
    }
  }
  return { hechos, fallidos };
}
