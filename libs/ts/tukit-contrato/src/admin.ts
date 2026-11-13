// Superficie del back-office (apps/admin) sobre pedidos y tickets.
//
// Extiende, sin tocar, los tipos de `comercio.ts` y `operacion.ts`: lo que el
// operador ve de mas (transaccion de Wompi, retractos con su plazo de la Ley
// 1480, la conversacion de un ticket) y lo que puede mandar de mas (despacho por
// transportadora, respuesta a un ticket). Todo sale solo para staff: comercio y
// operacion lo gatean por rol y responden 401/403/503 como el resto.

import type { Dinero } from "./contrato";
import type { Caso, EstadoCaso, Prioridad } from "./operacion";
import type {
  EstadoPedido,
  Pago,
  PedidoConHistorial,
  SolicitudAvancePedido,
} from "./comercio";

/** El pago tal como lo ve el staff: ademas de la referencia, el id de la
 *  transaccion de Wompi (`null` mientras el pago siga iniciado). Nunca datos de
 *  tarjeta (SG-03). */
export interface PagoAdmin extends Pago {
  transaccion_wompi: string | null;
  /** Ultimo cambio de estado del pago; para uno aprobado, la confirmacion. */
  actualizado_en: string | null;
}

/** Un retracto o devolucion (FU-04) con su plazo de la Ley 1480, art. 47:
 *  cinco dias habiles desde la entrega para ejercerlo y treinta dias calendario
 *  para reembolsar. Las fechas son dias `YYYY-MM-DD` de Bogota. */
export interface DevolucionAdmin {
  devolucion_id: string;
  motivo: string;
  monto: Dinero;
  creado_en: string;
  /** Ultimo dia para retractarse; `null` mientras el pedido no se entrega (el plazo corre desde la entrega). */
  plazo_retracto: string | null;
  dentro_de_plazo: boolean;
  limite_reembolso: string;
}

/** El detalle de pedido para el back-office. */
export interface PedidoAdmin extends Omit<PedidoConHistorial, "pago"> {
  pago: PagoAdmin | null;
  devoluciones: DevolucionAdmin[];
}

/** Lo que el admin manda a `/avanzar`: lo de siempre mas el despacho por
 *  transportadora (con ella, la guia es obligatoria; sin ella rige el reparto propio). */
export interface SolicitudAvanceAdmin extends SolicitudAvancePedido {
  transportadora?: string;
  guia?: string;
}

// ------------------------------------------------------------------ Tickets

/** Una entrada de la historia de un ticket. `respuesta` lleva el texto que se le
 *  mando al acudiente; `estado` el cambio (`desde`/`hacia`); `pedido` el vinculo. */
export interface EventoCasoAdmin {
  tipo: "respuesta" | "estado" | "pedido" | "asignacion" | "prioridad" | "nota_interna" | string;
  datos: Record<string, unknown>;
  actor_id: string | null;
  creado_en: string;
}

/** Un ticket con su cuerpo, su titular y su conversacion. `usuario_id` sirve para
 *  resolver el correo del acudiente contra el padron de identidad; el contacto no
 *  se guarda en operacion. */
export interface CasoDetalleAdmin extends Caso {
  descripcion: string;
  usuario_id: string | null;
  resuelto_en: string | null;
  eventos: EventoCasoAdmin[];
}

/** Los estados a los que el operador puede mover un ticket desde cada uno. Espejo
 *  de `TRANSICIONES_CASO` en `operacion/dominio/casos.py`; si se desalinean, el
 *  backend responde 409 y la pantalla muestra su mensaje. */
export const TRANSICIONES_CASO: Record<EstadoCaso, readonly EstadoCaso[]> = {
  abierto: ["en_gestion", "esperando_tercero", "resuelto"],
  en_gestion: ["esperando_tercero", "resuelto"],
  esperando_tercero: ["en_gestion", "resuelto"],
  resuelto: ["en_gestion", "cerrado"],
  cerrado: [],
};

/** El tope de una respuesta, igual que `LONGITUD_MAXIMA_RESPUESTA` del backend. */
export const LONGITUD_MAXIMA_RESPUESTA = 2000;

// ----------------------------------------- Fase 4: reconciliar, previa y lote

/** Resultado de preguntarle a Wompi por el pago de un pedido atascado. */
export type ResultadoReconciliacion = "pagado" | "en_curso" | "libre";

export interface RespuestaReconciliacion {
  pedido_id: string;
  resultado: ResultadoReconciliacion;
  estado_pedido: EstadoPedido;
}

/** Un paso de la linea de tiempo que ve el acudiente (`LineaDeTiempoPedido`). */
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

/** Lo que el acudiente veria hoy y despues de mover el pedido a `destino`. */
export interface VistaPreviaPedido {
  ahora: LineaVistaPrevia;
  despues: LineaVistaPrevia | null;
  /** Tipo del aviso que recibiria (`pedido_despachado`...), o `null`. */
  aviso: string | null;
  /** Si la matriz permite ese avance desde el estado actual. */
  legal: boolean;
}

/** Los destinos que admite el avance en lote (los que no piden datos). */
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

/** Quien llama se asigna el ticket ("yo") o lo suelta ("nadie"). */
export type AsignacionCaso = "yo" | "nadie";
export type PrioridadCaso = Prioridad;
