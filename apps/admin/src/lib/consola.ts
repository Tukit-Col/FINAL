// Los textos de la consola de revisión del admin, separados para poder
// probarlos con `node --test`.
//
// `TITULO_CLASE` del contrato está escrito para el acudiente ("En tu carrito",
// "Lo está revisando una persona") y lo usa la web: no se toca. El admin lee
// los mismos grupos con lo que tiene que HACER con cada uno; el resto de las
// clases conserva el título del contrato (`tituloClaseAdmin`).
//
// Solo importa tipos del contrato: corre igual en Next que en `node --test`.

import type { ClaseLinea } from "@tukit/contrato";

export const TITULO_CLASE_ADMIN: Partial<Record<ClaseLinea, string>> = {
  pendiente_revision: "Dudosas: confirma el producto",
  hueco: "No lo tenemos",
  sin_match: "No entendimos qué pide",
  licencia_digital: "Se paga por fuera",
  comprable: "Resueltas",
};

/** El título de un grupo en la consola; `contrato` es el `TITULO_CLASE` de la web. */
export function tituloClaseAdmin(
  clase: ClaseLinea,
  contrato: Readonly<Record<ClaseLinea, string>>,
): string {
  return TITULO_CLASE_ADMIN[clase] ?? contrato[clase];
}

/** La cabecera de un trabajo: "N dudosas sin decidir · M huecos". */
export function resumenPendientes(sinDecidir: number, huecos: number): string {
  const dudosas = `${sinDecidir} ${sinDecidir === 1 ? "dudosa" : "dudosas"} sin decidir`;
  return `${dudosas} · ${huecos} ${huecos === 1 ? "hueco" : "huecos"}`;
}
