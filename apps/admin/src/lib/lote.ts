// El cuerpo con que se valida una línea "confirmando el elegido", separado de
// los componentes para poder probarlo con `node --test`.
//
// Se manda SIEMPRE el sku del producto elegido y no `{}`: una línea que el
// sistema dejó dudosa puede no tener candidato registrado, y un `{}` le pedía
// al backend adivinar cuál confirmar. Con el sku, el backend valida justo el
// producto que el admin está viendo (y lo registra como candidato si hace
// falta). Una línea sin producto no se manda: no hay nada que confirmar.

import type { LineaKit, ValidarLinea } from "@tukit/contrato";

/** El cuerpo de "confirmo el elegido", o null si la línea no tiene producto. */
export function cuerpoValidarElegido(linea: Pick<LineaKit, "producto_elegido">): ValidarLinea | null {
  const sku = linea.producto_elegido?.sku;
  return sku ? { sku } : null;
}
