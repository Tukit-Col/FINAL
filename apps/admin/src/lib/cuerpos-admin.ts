export type Validado<T> = { ok: true; valor: T } | { ok: false; campo: string; mensaje: string };

const DESTINOS_LOTE = ["en_preparacion", "en_reparto", "entregado"] as const;
const PRIORIDADES = ["urgente", "alta", "media", "baja"] as const;
export const MAX_LOTE = 50;
export const MAX_NOTA = 2000;

function falla(campo: string, mensaje: string): { ok: false; campo: string; mensaje: string } {
  return { ok: false, campo, mensaje };
}

export function validarLote(
  cuerpo: unknown,
): Validado<{ pedido_ids: string[]; destino: (typeof DESTINOS_LOTE)[number] }> {
  const c = (cuerpo ?? {}) as { pedido_ids?: unknown; destino?: unknown };
  if (!Array.isArray(c.pedido_ids) || c.pedido_ids.length === 0 || !c.pedido_ids.every((i) => typeof i === "string")) {
    return falla("pedido_ids", "Elige al menos un pedido.");
  }
  if (c.pedido_ids.length > MAX_LOTE) return falla("pedido_ids", `Máximo ${MAX_LOTE} pedidos por lote.`);
  if (new Set(c.pedido_ids).size !== c.pedido_ids.length) return falla("pedido_ids", "Hay pedidos repetidos.");
  if (typeof c.destino !== "string" || !(DESTINOS_LOTE as readonly string[]).includes(c.destino)) {
    return falla("destino", "Ese destino no se puede mover en lote.");
  }
  return {
    ok: true,
    valor: { pedido_ids: c.pedido_ids as string[], destino: c.destino as (typeof DESTINOS_LOTE)[number] },
  };
}

export function validarAsignacion(cuerpo: unknown): Validado<"yo" | "nadie"> {
  const a = (cuerpo as { asignar?: unknown } | null)?.asignar;
  return a === "yo" || a === "nadie" ? { ok: true, valor: a } : falla("asignar", "Falta si asignas o sueltas el ticket.");
}

export function validarPrioridad(cuerpo: unknown): Validado<(typeof PRIORIDADES)[number]> {
  const p = (cuerpo as { prioridad?: unknown } | null)?.prioridad;
  return typeof p === "string" && (PRIORIDADES as readonly string[]).includes(p)
    ? { ok: true, valor: p as (typeof PRIORIDADES)[number] }
    : falla("prioridad", "Esa prioridad no existe.");
}

export function validarNota(cuerpo: unknown): Validado<string> {
  const t = (cuerpo as { texto?: unknown } | null)?.texto;
  if (typeof t !== "string" || !t.trim()) return falla("texto", "Escribe la nota.");
  if (t.trim().length > MAX_NOTA) return falla("texto", `La nota pasa de ${MAX_NOTA} caracteres.`);
  return { ok: true, valor: t.trim() };
}

export function validarDestinoDePrevia(destino: string | null): Validado<string> {
  return destino && /^[a-z_]{1,24}$/.test(destino)
    ? { ok: true, valor: destino }
    : falla("destino", "Falta el estado destino.");
}
