// Helpers puros de la sección "Métricas" del perfil de un colegio. Viven aquí,
// sin dependencias de React ni del origen, para poder probarlos con `node
// --test` sin levantar nada (ver `apps/admin/test/metricas-colegio.test.ts`).

import type { Sugerencia } from "@tukit/contrato";

/** La demanda de un grado SIN lista verificada: cuántas familias distintas la
 *  han pedido. Se cuenta una tarea por familia, no versiones. */
export interface DemandaGrado {
  grado: string;
  solicitudes: number;
}

/** Grados sin lista verificada ordenados por demanda (más pedidos primero).
 *
 * "Demanda" = tareas `origen='sugerencia_padre'` de ESTE colegio que aún
 * esperan una lista para el grado. El discriminador clave es
 * `contacto_referencia !== null`: al "Editar (nueva versión)" el catálogo clona
 * la tarea conservando `origen='sugerencia_padre'` pero ANULANDO
 * `contacto_referencia`, así que contar por `origen` a secas inflaría la demanda
 * con las copias de edición. Contando solo las que conservan contacto, cada
 * solicitud real de un padre cuenta una vez y ninguna copia suma.
 *
 * Solo se devuelven los grados que NO tienen lista verificada (los que ya la
 * tienen no son "demanda pendiente"). Empates: por nombre de grado, orden
 * estable. */
export function demandaPorGrado(
  sugerencias: Sugerencia[],
  colegioId: string,
  gradosVerificados: ReadonlySet<string>,
): DemandaGrado[] {
  const conteo = new Map<string, number>();
  for (const s of sugerencias) {
    if (s.colegio_id !== colegioId) continue;
    if (s.contacto_referencia === null) continue; // copia de "nueva versión": no es demanda
    if (!s.grado) continue;
    if (gradosVerificados.has(s.grado)) continue; // ya tiene lista: no es demanda pendiente
    conteo.set(s.grado, (conteo.get(s.grado) ?? 0) + 1);
  }
  return [...conteo.entries()]
    .map(([grado, solicitudes]) => ({ grado, solicitudes }))
    .sort((a, b) => b.solicitudes - a.solicitudes || a.grado.localeCompare(b.grado));
}
