// La ruta de "Recibimos tu lista", separada del formulario para poder probarla
// sin navegador. Cuenta las listas que se subieron y, aparte, las que quedaron
// diferidas: con el catalogo caido la subida igual responde y la lista queda
// guardada en Tukit, sin version todavia (`version_id: null`, `estado:
// "pendiente"`, ADR 0040). Esas pasan solas a la fila de revision cuando el
// catalogo vuelve, y la pantalla se lo dice al acudiente para que no la suba
// otra vez.

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

// Lo que llega por la URL no es de fiar: un numero raro no muestra el aviso y
// nunca hay mas diferidas que listas.
export function cuantasDiferidas(diferidas: string | undefined, cuantas: number): number {
  const valor = Math.floor(Number(diferidas));
  if (!Number.isFinite(valor) || valor < 1) return 0;
  return Math.min(valor, cuantas);
}
