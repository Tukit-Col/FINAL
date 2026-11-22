export type TonoEstado = "exito" | "aviso" | "peligro" | "info" | "neutro";

export function proporcion(valor: number, maximo: number, piso = 4): number {
  if (!(valor > 0)) return 0;
  const tope = maximo > 0 ? maximo : 1;
  return Math.min(100, Math.max(piso, (valor / tope) * 100));
}
