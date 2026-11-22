import type { EstadoPedido, PedidoAdmin } from "@tukit/contrato";

export function enmascararCorreo(correo: string | null | undefined): string {
  if (!correo) return "—";
  const arroba = correo.lastIndexOf("@");
  if (arroba <= 0) return "***";
  return `${correo[0]}***${correo.slice(arroba)}`;
}

export function enmascararTelefono(telefono: string | null | undefined): string {
  if (!telefono) return "—";
  const digitos = telefono.replace(/\D/g, "");
  if (digitos.length < 4) return "•••";
  return `••• ••• ${digitos.slice(-4)}`;
}

export function rotuloDeHijo(h: { grado: string }, indice = 0): string {
  return `Hijo ${indice + 1} · grado ${h.grado}`;
}

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
  cuando: string | null;
  quien: string | null;
}

function rango(estado: string): number {
  return PASOS_CADENA.indexOf(estado as (typeof PASOS_CADENA)[number]);
}

export function construirLineaDeTiempo(pedido: PedidoAdmin): PasoDeTiempo[] {
  const alcanzados = new Map<number, { cuando: string; quien: string | null }>();
  alcanzados.set(0, { cuando: pedido.creado_en, quien: "Tukit" });

  const pagoConfirmado = pedido.pago !== null && ["aprobado", "reembolsado"].includes(pedido.pago.estado);
  if (pagoConfirmado && pedido.pago?.actualizado_en) {
    alcanzados.set(1, { cuando: pedido.pago.actualizado_en, quien: "Wompi" });
  }
  for (const h of pedido.historial) {
    const r = rango(h.estado_hacia);
    if (r > 0 && !alcanzados.has(r)) alcanzados.set(r, { cuando: h.creado_en, quien: h.actor_correo });
  }
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

export function totalDescuadrado(pedido: PedidoAdmin): boolean {
  return lineasConSubtotal(pedido).reduce((s, l) => s + l.subtotal, 0) !== pedido.total;
}

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
