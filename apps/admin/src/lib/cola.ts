// Cómo se reparte la cola de trabajos en espera, separado de las páginas para
// poder probarlo con `node --test` y para que `/cola` y el inicio cuenten lo
// mismo.
//
// Una vista previa de lista (`preview_onboarding`) también queda en
// `espera_revision`, pero no es un acudiente esperando: es el borrador que el
// admin ajusta antes de aprobar la lista. Contarla como "trabajo de acudiente
// en espera" inflaba la cola, así que va aparte y enlaza a su revisor.

import type { EntradaCola } from "@tukit/contrato";

export const ORIGEN_VISTA_PREVIA = "preview_onboarding";

export interface ColaSeparada {
  // Trabajos en espera con un acudiente (o un grado) detrás.
  deAcudiente: EntradaCola[];
  // Vistas previas de lista en espera; se revisan desde `/onboarding/{version_id}`.
  vistasPrevias: EntradaCola[];
}

/** Las entradas en `espera_revision`, separadas en de acudiente y vistas previas. */
export function separarCola(entradas: readonly EntradaCola[]): ColaSeparada {
  const enEspera = entradas.filter((e) => e.estado === "espera_revision");
  return {
    deAcudiente: enEspera.filter((e) => e.origen !== ORIGEN_VISTA_PREVIA),
    vistasPrevias: enEspera.filter((e) => e.origen === ORIGEN_VISTA_PREVIA),
  };
}
