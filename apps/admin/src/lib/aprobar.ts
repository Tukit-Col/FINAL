// La guarda de "Aprobar y publicar" en la región 4 del revisor, separada del
// componente para poder probarla con `node --test`.
//
// Aprobar la lista hace cosas distintas según su vista previa (ver el poller
// de Inteligencia): si está al día, ESA vista previa pasa a ser el kit del
// grado (y el del acudiente, si hay uno); si no hay o la lista cambió, se arma
// un kit desde cero. La guarda le dice al revisor cuál de los dos va a pasar
// antes de que apruebe, y lo frena solo cuando aprobar tiraría sus ajustes sin
// que lo sepa (la lista cambió después de previsualizar).
//
// Solo importa tipos del contrato: corre igual en Next que en `node --test`.

import type { VistaPreviaLista } from "@tukit/contrato";

export type GuardaAprobacion =
  // No se puede aprobar: la vista previa ya no corresponde a la lista.
  | { tipo: "bloqueada"; mensaje: string }
  // Se puede, pero hay que confirmarlo: el kit queda en la Cola.
  | { tipo: "confirmar"; mensaje: string; trabajoId: string }
  // Se puede; solo se informa qué pasará.
  | { tipo: "aviso"; mensaje: string }
  | { tipo: "libre" };

/**
 * Qué hace "Aprobar y publicar" con esta vista previa.
 *
 * `vistaPrevia` es `undefined` cuando no se pudo leer (el catálogo no
 * respondió): no se sabe si se conservarán los ajustes, y se dice así en vez
 * de afirmar que no hay vista previa.
 */
export function guardaDeAprobacion(
  vistaPrevia: VistaPreviaLista | null | undefined,
  tieneContacto: boolean,
): GuardaAprobacion {
  if (vistaPrevia === undefined) {
    return {
      tipo: "aviso",
      mensaje:
        "No pudimos leer la vista previa: no sabemos si al aprobar se conservarán sus ajustes.",
    };
  }
  if (vistaPrevia === null) {
    return {
      tipo: "aviso",
      mensaje: tieneContacto
        ? "Sin vista previa: al aprobar se arma el kit del acudiente desde cero y se le publica directo."
        : "Sin vista previa: al aprobar se arma un kit nuevo que quedará en la Cola para revisar.",
    };
  }
  // La desactualización gana a las dudosas: aprobar ahora ni siquiera usaría
  // esa vista previa, así que decidir sus dudosas no serviría de nada.
  if (vistaPrevia.desactualizada) {
    return {
      tipo: "bloqueada",
      mensaje: "La lista cambió después de previsualizar: vuelve a previsualizar",
    };
  }
  const n = vistaPrevia.lineas_sin_decidir;
  if (n > 0) {
    return {
      tipo: "confirmar",
      mensaje: `Quedan ${n} ${n === 1 ? "dudosa" : "dudosas"}. La lista se aprueba, pero el kit queda en la Cola hasta que las decidas.`,
      trabajoId: vistaPrevia.trabajo_id,
    };
  }
  return { tipo: "libre" };
}
