// Lógica pura de `POST /api/onboarding`: de los campos del formulario al
// colegio designado que viaja a inteligencia. Separada de la ruta para probarla
// con `node --test`.
//
// El buscador de la cola ya reconduce por DANE (una entrada del directorio que
// es de un colegio de Tukit se elige como ese colegio), pero la ruta no confía
// en la pantalla: si llega un DANE que ya tiene dueño, se manda su `colegio_id`.
// Si no, inteligencia derivaría un id nuevo del DANE y el colegio quedaría
// duplicado en la aprobación.

import type { ColegioBuscable, ColegioDesignado } from "@tukit/contrato";

function texto(valor: unknown): string {
  return typeof valor === "string" ? valor.trim() : "";
}

export function designarColegio(
  campos: { colegio_id?: unknown; colegio_dane?: unknown; colegio_nombre?: unknown },
  colegios: readonly Pick<ColegioBuscable, "colegio_id" | "dane">[],
): ColegioDesignado | null {
  const colegioId = texto(campos.colegio_id);
  if (colegioId) return { colegio_id: colegioId };
  const dane = texto(campos.colegio_dane);
  const nombre = texto(campos.colegio_nombre);
  if (dane) {
    const conocido = colegios.find((c) => c.dane === dane);
    if (conocido) return { colegio_id: conocido.colegio_id };
    // Del directorio sin nombre no se sabe cómo mostrarlo en la cola.
    return nombre ? { colegio_dane: dane, colegio_nombre: nombre } : null;
  }
  return nombre ? { colegio_nombre: nombre } : null;
}
