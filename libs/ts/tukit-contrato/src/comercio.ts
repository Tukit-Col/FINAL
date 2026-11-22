import type { Dinero } from "./contrato";

export const VERSION_COMERCIO_ASUMIDA = "1.x-asumida";

export type EstadoPedido =
  | "pendiente_pago"
  | "pagado"
  | "en_preparacion"
  | "despachado"
  | "en_reparto"
  | "entregado"
  | "incidencia"
  | "cancelado";

export const ESTADOS_PEDIDO: readonly EstadoPedido[] = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
  "incidencia",
  "cancelado",
];

export const ETIQUETA_ESTADO_PEDIDO: Record<EstadoPedido, string> = {
  pendiente_pago: "Pendiente de pago",
  pagado: "Pagado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
  incidencia: "Con incidencia",
  cancelado: "Cancelado",
};

export type EstadoPago = "iniciado" | "aprobado" | "rechazado" | "reembolsado";

export interface Pago {
  referencia_wompi: string;
  metodo: "pse" | "nequi" | "tarjeta";
  estado: EstadoPago;
  monto: Dinero;
}

export interface Envio {
  destinatario: string;
  direccion: string;
  ciudad: string;
  telefono: string | null;
  departamento: string | null;
  documento_destinatario: string | null;
  indicaciones: string | null;
  localidad: string | null;
  latitud: number | null;
  longitud: number | null;
  transportadora: string | null;
  guia: string | null;
  repartidor_nombre: string | null;
  repartidor_celular?: string | null;
  entrega_estimada: string | null;
  entregado_en: string | null;
}

export interface LineaPedido {
  sku: string;
  nombre: string;
  cantidad: number;
  precio_unitario: Dinero;
}

export interface PasoDePedido {
  estado: EstadoPedido;
  en: string;
  etiqueta: string;
}

export interface EstadoRetracto {
  puede: boolean;
  razon:
    | "ya_solicitado"
    | "plazo_vencido"
    | "sin_pagar"
    | "cancelado"
    | "sin_fecha_de_entrega"
    | "estado_no_permite"
    | null;
  vence_en: string | null;
  antes_de_entrega: boolean;
  solicitado_en: string | null;
}

export interface RetractoSolicitado {
  devolucion_id: string;
  pedido_id: string;
  cancelado: boolean;
  estado: EstadoPedido;
  monto: Dinero;
}

export interface Pedido {
  pedido_id: string;
  usuario_id: string;
  trabajo_id: string | null;
  estado: EstadoPedido;
  creado_en: string;
  total: Dinero;
  hijos: number;
  colegios: string[];
  lineas: LineaPedido[];
  pago: Pago | null;
  envio: Envio | null;
  seguimiento?: PasoDePedido[];
  retracto?: EstadoRetracto;
  linea_de_tiempo?: LineaDeTiempoPedido;
  alertas?: AlertaPedido[];
}

export type AlertaPedido = "pagado_sin_avanzar" | "pago_atascado" | "incidencia_abierta";

export const ALERTAS_PEDIDO: readonly AlertaPedido[] = [
  "pagado_sin_avanzar",
  "pago_atascado",
  "incidencia_abierta",
];

export const ETIQUETA_ALERTA_PEDIDO: Record<AlertaPedido, string> = {
  pagado_sin_avanzar: "Pagado sin avanzar",
  pago_atascado: "Pago atascado",
  incidencia_abierta: "Incidencia abierta",
};

export type TipoIncidencia = "no_habia_nadie" | "direccion_errada" | "rechazado" | "otro";

export const TIPOS_INCIDENCIA: readonly TipoIncidencia[] = [
  "no_habia_nadie",
  "direccion_errada",
  "rechazado",
  "otro",
];

export const ETIQUETA_TIPO_INCIDENCIA: Record<TipoIncidencia, string> = {
  no_habia_nadie: "No había nadie",
  direccion_errada: "Dirección errada",
  rechazado: "Rechazado",
  otro: "Otro",
};

export interface EntradaHistorialPedido {
  estado_desde: EstadoPedido;
  estado_hacia: EstadoPedido;
  actor_id: string;
  actor_correo: string | null;
  nota: string | null;
  tipo_incidencia: string | null;
  creado_en: string;
}

export interface PedidoConHistorial extends Pedido {
  historial: EntradaHistorialPedido[];
}

export type PasoPedido =
  | "creado"
  | "pagado"
  | "en_preparacion"
  | "despachado"
  | "en_reparto"
  | "entregado";

export const ETIQUETA_PASO_PEDIDO: Record<PasoPedido, string> = {
  creado: "Pedido creado",
  pagado: "Pago confirmado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
};

export const PASOS_PEDIDO: readonly PasoPedido[] = [
  "creado",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
];

export const FASES_SEGUIMIENTO: readonly PasoPedido[] = PASOS_PEDIDO.filter((p) => p !== "creado");

export const ETIQUETA_FASE_SEGUIMIENTO: Record<PasoPedido, string> = {
  ...ETIQUETA_PASO_PEDIDO,
  en_preparacion: "Preparando tu kit",
};

export type SituacionPaso = "hecho" | "actual" | "futuro";

export interface PasoLineaDeTiempo {
  paso: PasoPedido;
  estado: SituacionPaso;
  fecha: string | null;
  repartidor_nombre?: string | null;
}

export type DesvioPedido =
  | { tipo: "incidencia"; tipo_incidencia: string | null; fecha: string | null }
  | { tipo: "cancelado"; fecha: string | null };

export interface LineaDeTiempoPedido {
  pasos: PasoLineaDeTiempo[];
  especial: DesvioPedido | null;
  entrega_estimada: string | null;
  pago_pendiente: { vence_en: string; vencido: boolean } | null;
}

export interface PedidoDelAcudiente extends Pedido {
  linea_de_tiempo: LineaDeTiempoPedido;
}

export interface SolicitudAvancePedido {
  destino: EstadoPedido;
  repartidor_nombre?: string;
  repartidor_celular?: string;
  tipo_incidencia?: TipoIncidencia;
  nota?: string;
  entrega_estimada?: string;
}

export interface ResumenComercio {
  pedidos_totales: number;
  por_estado: Record<EstadoPedido, number>;
  ingresos_confirmados: Dinero;
  entregas_pendientes: number;
  alertas?: Record<AlertaPedido, number>;
}

export interface TableroComercio {
  resumen: ResumenComercio;
  pedidos: Pedido[];
}

export function pedidoEnCurso(pedido: Pedido): boolean {
  return (
    pedido.estado === "pagado" ||
    pedido.estado === "en_preparacion" ||
    pedido.estado === "despachado" ||
    pedido.estado === "en_reparto"
  );
}
