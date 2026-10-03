// Las reglas de "Mis pedidos", separadas de las rutas para poder probarlas sin
// servidor: el pedido tiene que ser del acudiente de la sesion y seguir
// pendiente de pago; pagarlo exige ademas que no haya vencido. Un pedido ajeno
// responde igual que uno inexistente, para no confirmar que el id existe.
//
// Comercio aplica las mismas reglas (y es quien manda); aqui se repiten para
// pintar el boton correcto y dar un mensaje claro sin ir y volver.

import type { EstadoPedido } from "@tukit/contrato";

// Igual que `VIGENCIA_PAGO` en Comercio: despues se cobraria un precio viejo.
export const VIGENCIA_PAGO_HORAS = 24;

type PedidoMinimo = { pedido_id: string; estado: EstadoPedido; creado_en: string };

export type AccionPedido = "pagar" | "cancelar";

export type DecisionPedido =
  | { ok: true }
  | { ok: false; estado: 404 | 409; error: string; mensaje: string };

export function pedidoVencido(creadoEn: string, ahora: number): boolean {
  return ahora - Date.parse(creadoEn) > VIGENCIA_PAGO_HORAS * 3600_000;
}

export function decidirAccionPedido(
  pedidosDelAcudiente: readonly PedidoMinimo[],
  pedidoId: string,
  accion: AccionPedido,
  ahora: number,
): DecisionPedido {
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
      error: "pedido_no_pendiente",
      mensaje: "Este pedido ya no está pendiente de pago.",
    };
  }
  // Un pedido vencido no se paga, pero si se cancela: asi se libera lo que
  // tenia reservado.
  if (accion === "pagar" && pedidoVencido(pedido.creado_en, ahora)) {
    return {
      ok: false,
      estado: 409,
      error: "pedido_vencido",
      mensaje: "Este pedido tiene más de 24 horas. Vuelve a armar tu kit para ver el precio de hoy.",
    };
  }
  return { ok: true };
}

// El color de la etiqueta de estado en "Mis pedidos": verde lo pagado y lo que
// va camino a la casa, amarillo lo que espera pago, rojo lo cancelado o con
// problema.
export type TonoEstado = "exito" | "aviso" | "peligro";

const TONO_ESTADO: Record<EstadoPedido, TonoEstado> = {
  pendiente_pago: "aviso",
  pagado: "exito",
  en_preparacion: "exito",
  despachado: "exito",
  en_reparto: "exito",
  entregado: "exito",
  incidencia: "peligro",
  cancelado: "peligro",
};

export function tonoEstadoPedido(estado: EstadoPedido): TonoEstado {
  return TONO_ESTADO[estado];
}

// El cruce entre "Mis solicitudes" y "Mis pedidos" por kit (trabajo_id). La
// solicitud no se cierra ni guarda un estado propio: se calcula cada vez, asi
// que si el pedido se cancela o se reembolsa, la solicitud vuelve sola a "Listo".
// - comprado: el kit tiene un pedido pagado o en camino (el mas reciente).
// - por_pagar: no lo tiene, pero hay uno pendiente de pago y vigente.
export type CompraSolicitud = { estado: "comprado" | "por_pagar"; pedidoId: string } | null;

const ESTADOS_COMPRADOS: ReadonlySet<EstadoPedido> = new Set([
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
]);

type PedidoDeKit = PedidoMinimo & { trabajo_id: string | null };

export function compraDeSolicitud(
  trabajoId: string,
  pedidos: readonly PedidoDeKit[],
  ahora: number,
): CompraSolicitud {
  const delKit = pedidos
    .filter((p) => p.trabajo_id === trabajoId)
    .sort((a, b) => Date.parse(b.creado_en) - Date.parse(a.creado_en));
  const comprado = delKit.find((p) => ESTADOS_COMPRADOS.has(p.estado));
  if (comprado) return { estado: "comprado", pedidoId: comprado.pedido_id };
  const pendiente = delKit.find(
    (p) => p.estado === "pendiente_pago" && !pedidoVencido(p.creado_en, ahora),
  );
  if (pendiente) return { estado: "por_pagar", pedidoId: pendiente.pedido_id };
  return null;
}
