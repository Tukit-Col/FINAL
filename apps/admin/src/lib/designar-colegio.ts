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
    return nombre ? { colegio_dane: dane, colegio_nombre: nombre } : null;
  }
  return nombre ? { colegio_nombre: nombre } : null;
}
