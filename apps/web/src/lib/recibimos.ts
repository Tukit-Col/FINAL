import type { SubidaHecha } from "@tukit/contrato";

export function esDiferida(subida: Pick<SubidaHecha, "version_id" | "estado">): boolean {
  return subida.estado === "pendiente" || subida.version_id === null;
}

export function rutaRecibimos(
  subidas: readonly Pick<SubidaHecha, "version_id" | "estado">[],
  trabajo?: string | null,
): string {
  const parametros = new URLSearchParams({ pendientes: String(subidas.length) });
  const diferidas = subidas.filter(esDiferida).length;
  if (diferidas > 0) parametros.set("diferidas", String(diferidas));
  if (trabajo) parametros.set("trabajo", trabajo);
  return `/recibimos?${parametros.toString()}`;
}

export function cuantasDiferidas(diferidas: string | undefined, cuantas: number): number {
  const valor = Math.floor(Number(diferidas));
  if (!Number.isFinite(valor) || valor < 1) return 0;
  return Math.min(valor, cuantas);
}
