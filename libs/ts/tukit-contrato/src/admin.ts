// Superficie del back-office (apps/admin) sobre pedidos y tickets.
//
// Extiende, sin tocar, los tipos de `comercio.ts` y `operacion.ts`: lo que el
// operador ve de mas (transaccion de Wompi, retractos con su plazo de la Ley
// 1480, la conversacion de un ticket) y lo que puede mandar de mas (despacho por
// transportadora, respuesta a un ticket). Todo sale solo para staff: comercio y
// operacion lo gatean por rol y responden 401/403/503 como el resto.

import type { Dinero } from "./contrato";
import type { Caso, EstadoCaso } from "./operacion";
import type {
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
  tipo: "respuesta" | "estado" | "pedido" | string;
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
