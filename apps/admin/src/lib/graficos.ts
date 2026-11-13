// Aritmetica compartida por las primitivas graficas del back-office (Barras,
// Columnas, Insignia). Pura, sin React, para `node --test`.

/** Tono semantico de una insignia de estado. */
export type TonoEstado = "exito" | "aviso" | "peligro" | "info" | "neutro";

/**
 * Largo de una barra en % de su pista. Un valor positivo nunca queda en 0 (se
 * leeria como "no hay nada"): minimo `piso`%. Un `maximo` <= 0 cuenta como 1.
 */
export function proporcion(valor: number, maximo: number, piso = 4): number {
  if (!(valor > 0)) return 0;
  const tope = maximo > 0 ? maximo : 1;
  return Math.min(100, Math.max(piso, (valor / tope) * 100));
}
