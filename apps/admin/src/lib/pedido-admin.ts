// La logica pura del detalle de pedido: linea de tiempo del estado, enmascarado
// de datos personales y totales de las lineas.
//
// Vive aparte de la pagina para probarse con `node --test` (sin runner de
// componentes), por eso SOLO importa tipos del contrato.

import type { EstadoPedido, PedidoAdmin } from "@tukit/contrato";

/** `maria@correo.com` -> `m***@correo.com`. El staff necesita reconocer la
 *  cuenta, no leerla entera; el correo completo no se pinta si no hace falta. */
export function enmascararCorreo(correo: string | null | undefined): string {
  if (!correo) return "—";
  const arroba = correo.lastIndexOf("@");
  if (arroba <= 0) return "***";
  return `${correo[0]}***${correo.slice(arroba)}`;
}

/** `3109998877` -> `••• ••• 8877`: se ven los ultimos cuatro digitos. */
export function enmascararTelefono(telefono: string | null | undefined): string {
  if (!telefono) return "—";
  const digitos = telefono.replace(/\D/g, "");
  if (digitos.length < 4) return "•••";
  return `••• ••• ${digitos.slice(-4)}`;
}

/** El rotulo de un hijo en las vistas admin: posicion estable y grado, nunca el
 *  apodo ni el nombre del menor (Ley 1581). `indice` parte en 0. */
export function rotuloDeHijo(h: { grado: string }, indice = 0): string {
  return `Hijo ${indice + 1} · grado ${h.grado}`;
}

/** Los pasos de la cadena de entrega, en orden, para la linea de tiempo. */
export const PASOS_CADENA = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
] as const satisfies readonly EstadoPedido[];

export const ETIQUETA_PASO: Record<(typeof PASOS_CADENA)[number], string> = {
  pendiente_pago: "Creado",
  pagado: "Pago confirmado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
};

export type SituacionPaso = "hecho" | "actual" | "pendiente";

export interface PasoDeTiempo {
  estado: (typeof PASOS_CADENA)[number];
  etiqueta: string;
  situacion: SituacionPaso;
  /** ISO del momento en que se llego al paso, o `null` si aun no ocurre. */
  cuando: string | null;
  /** Quien lo hizo: el correo del operador, "Wompi" para el pago, "Tukit" para la creacion. */
  quien: string | null;
}

function rango(estado: string): number {
  return PASOS_CADENA.indexOf(estado as (typeof PASOS_CADENA)[number]);
}

/** La linea de tiempo del pedido: cada paso de la cadena con su situacion,
 *  su fecha y su responsable.
 *
 *  El pago lo confirma el webhook de Wompi y no deja fila en el historial, asi
 *  que su momento sale del pago aprobado. El resto sale del historial: la primera
 *  vez que el pedido llego a ese estado. Un pedido en `incidencia` o `cancelado`
 *  conserva el ultimo paso de la cadena alcanzado como `actual`; la incidencia y
 *  la cancelacion se muestran aparte, en el historial. */
export function construirLineaDeTiempo(pedido: PedidoAdmin): PasoDeTiempo[] {
  const alcanzados = new Map<number, { cuando: string; quien: string | null }>();
  alcanzados.set(0, { cuando: pedido.creado_en, quien: "Tukit" });

  const pagoConfirmado = pedido.pago !== null && ["aprobado", "reembolsado"].includes(pedido.pago.estado);
  if (pagoConfirmado && pedido.pago?.actualizado_en) {
    alcanzados.set(1, { cuando: pedido.pago.actualizado_en, quien: "Wompi" });
  }
  for (const h of pedido.historial) {
    const r = rango(h.estado_hacia);
    // Solo la primera vez: un "Reprogramar" que vuelve a preparacion no reescribe la fecha original.
    if (r > 0 && !alcanzados.has(r)) alcanzados.set(r, { cuando: h.creado_en, quien: h.actor_correo });
  }
  // Un pedido ya pagado sin fecha de pago (dato viejo) igual cuenta el paso como hecho.
  const rangoActual = rango(pedido.estado);
  if (rangoActual >= 1 && !alcanzados.has(1) && pagoConfirmado) {
    alcanzados.set(1, { cuando: pedido.creado_en, quien: "Wompi" });
  }

  const masAlto = Math.max(...alcanzados.keys());
  return PASOS_CADENA.map((estado, i) => {
    const dato = alcanzados.get(i);
    const situacion: SituacionPaso = i < masAlto ? (dato ? "hecho" : "pendiente") : i === masAlto ? "actual" : "pendiente";
    return {
      estado,
      etiqueta: ETIQUETA_PASO[estado],
      situacion,
      cuando: dato?.cuando ?? null,
      quien: dato?.quien ?? null,
    };
  });
}

export interface LineaConSubtotal {
  sku: string;
  nombre: string;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
}

export function lineasConSubtotal(pedido: PedidoAdmin): LineaConSubtotal[] {
  return pedido.lineas.map((l) => ({
    sku: l.sku,
    nombre: l.nombre,
    cantidad: l.cantidad,
    precio_unitario: l.precio_unitario,
    subtotal: l.cantidad * l.precio_unitario,
  }));
}

/** `true` si el total guardado no coincide con la suma de las lineas: una
 *  señal para el operador, no un error (el total se congela al confirmar). */
export function totalDescuadrado(pedido: PedidoAdmin): boolean {
  return lineasConSubtotal(pedido).reduce((s, l) => s + l.subtotal, 0) !== pedido.total;
}

/** Texto de la fecha de un plazo `YYYY-MM-DD` ("lun 9 nov 2026") sin pasar por
 *  `Date` en zona local: el dia ya es de Bogota y no debe correrse. */
export function formatearDiaIso(dia: string | null): string {
  if (!dia || !/^\d{4}-\d{2}-\d{2}$/.test(dia)) return "—";
  const [a, m, d] = dia.split("-").map(Number);
  const fecha = new Date(Date.UTC(a, m - 1, d));
  return new Intl.DateTimeFormat("es-CO", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(fecha);
}
