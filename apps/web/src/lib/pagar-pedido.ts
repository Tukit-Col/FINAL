import type { EstadoPedido } from "@tukit/contrato";

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

export type CompraSolicitud = { estado: "comprado" | "por_pagar"; pedidoId: string } | null;

const ESTADOS_COMPRADOS: ReadonlySet<EstadoPedido> = new Set([
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
  "incidencia",
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

export interface EntregaPrevia {
  destinatario: string;
  direccion: string;
  ciudad: string;
  indicaciones: string;
  localidad: string;
  departamento: string;
  latitud: number | null;
  longitud: number | null;
}

type EnvioMinimo = {
  destinatario: string;
  direccion: string;
  ciudad: string;
  indicaciones: string | null;
  localidad: string | null;
  departamento: string | null;
  latitud?: number | null;
  longitud?: number | null;
};

export function entregaParaReintento(
  pedidos: readonly (PedidoDeKit & { envio: EnvioMinimo | null })[],
  trabajoId: string,
  ahora: number,
): EntregaPrevia | null {
  const pedido = pedidos
    .filter(
      (p) =>
        p.trabajo_id === trabajoId &&
        p.estado === "pendiente_pago" &&
        !pedidoVencido(p.creado_en, ahora) &&
        p.envio !== null,
    )
    .sort((a, b) => Date.parse(b.creado_en) - Date.parse(a.creado_en))[0];
  if (!pedido?.envio) return null;
  const e = pedido.envio;
  return {
    destinatario: e.destinatario,
    direccion: e.direccion,
    ciudad: e.ciudad,
    indicaciones: e.indicaciones ?? "",
    localidad: e.localidad ?? "",
    departamento: e.departamento ?? "",
    latitud: e.latitud ?? null,
    longitud: e.longitud ?? null,
  };
}
