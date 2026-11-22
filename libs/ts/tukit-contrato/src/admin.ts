import type { Dinero } from "./contrato";
import type { Caso, EstadoCaso, Prioridad } from "./operacion";
import type {
  EstadoPedido,
  Pago,
  PedidoConHistorial,
  SolicitudAvancePedido,
} from "./comercio";

export interface PagoAdmin extends Pago {
  transaccion_wompi: string | null;
  actualizado_en: string | null;
}

export interface DevolucionAdmin {
  devolucion_id: string;
  motivo: string;
  monto: Dinero;
  creado_en: string;
  plazo_retracto: string | null;
  dentro_de_plazo: boolean;
  limite_reembolso: string;
}

export interface PedidoAdmin extends Omit<PedidoConHistorial, "pago"> {
  pago: PagoAdmin | null;
  devoluciones: DevolucionAdmin[];
}

export interface SolicitudAvanceAdmin extends SolicitudAvancePedido {
  transportadora?: string;
  guia?: string;
}

export interface EventoCasoAdmin {
  tipo: "respuesta" | "estado" | "pedido" | "asignacion" | "prioridad" | "nota_interna" | string;
  datos: Record<string, unknown>;
  actor_id: string | null;
  creado_en: string;
}

export interface CasoDetalleAdmin extends Caso {
  descripcion: string;
  usuario_id: string | null;
  resuelto_en: string | null;
  eventos: EventoCasoAdmin[];
}

export const TRANSICIONES_CASO: Record<EstadoCaso, readonly EstadoCaso[]> = {
  abierto: ["en_gestion", "esperando_tercero", "resuelto"],
  en_gestion: ["esperando_tercero", "resuelto"],
  esperando_tercero: ["en_gestion", "resuelto"],
  resuelto: ["en_gestion", "cerrado"],
  cerrado: [],
};

export const LONGITUD_MAXIMA_RESPUESTA = 2000;

export type ResultadoReconciliacion = "pagado" | "en_curso" | "libre";

export interface RespuestaReconciliacion {
  pedido_id: string;
  resultado: ResultadoReconciliacion;
  estado_pedido: EstadoPedido;
}

export interface PasoVistaPrevia {
  paso: string;
  estado: "hecho" | "actual" | "futuro";
  fecha: string | null;
  repartidor_nombre?: string | null;
}

export interface LineaVistaPrevia {
  pasos: PasoVistaPrevia[];
  especial: { tipo: "incidencia" | "cancelado"; fecha: string | null; tipo_incidencia?: string | null } | null;
  entrega_estimada: string | null;
  pago_pendiente: { vence_en: string; vencido: boolean } | null;
}

export interface VistaPreviaPedido {
  ahora: LineaVistaPrevia;
  despues: LineaVistaPrevia | null;
  aviso: string | null;
  legal: boolean;
}

export type DestinoDeLote = "en_preparacion" | "en_reparto" | "entregado";
export const DESTINOS_DE_LOTE: readonly DestinoDeLote[] = ["en_preparacion", "en_reparto", "entregado"];
export const MAX_PEDIDOS_POR_LOTE = 50;

export interface SolicitudLote {
  pedido_ids: string[];
  destino: DestinoDeLote;
}

export interface RespuestaLote {
  avanzados: string[];
  fallidos: { pedido_id: string; codigo: string; mensaje: string }[];
}

export type AsignacionCaso = "yo" | "nadie";
export type PrioridadCaso = Prioridad;
