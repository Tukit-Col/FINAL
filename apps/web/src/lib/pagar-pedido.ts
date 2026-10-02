// La regla de "Pagar" en Mis pedidos, separada de la ruta para poder probarla
// sin servidor: el pedido tiene que ser del acudiente de la sesion y seguir
// pendiente de pago. Un pedido ajeno responde igual que uno inexistente, para
// no confirmar que el id existe.

import type { EstadoPedido } from "@tukit/contrato";

type PedidoMinimo = { pedido_id: string; estado: EstadoPedido };

export type DecisionPago =
  | { ok: true }
  | { ok: false; estado: 404 | 409; error: string; mensaje: string };

export function decidirPagoPedido(
  pedidosDelAcudiente: readonly PedidoMinimo[],
  pedidoId: string,
): DecisionPago {
  const pedido = pedidosDelAcudiente.find((p) => p.pedido_id === pedidoId);
  if (!pedido) {
    return {
      ok: false,
      estado: 404,
      error: "pedido_no_existe",
      mensaje: "No encontramos ese pedido en tu cuenta.",
    };
  }
  if (pedido.estado !== "pendiente_pago") {
    return {
      ok: false,
      estado: 409,
      error: "pedido_no_pagable",
      mensaje: "Este pedido ya no está pendiente de pago.",
    };
  }
  return { ok: true };
}
