import type { EstadoTrabajo, Solicitud } from "@tukit/contrato";
import type { TonoEstado } from "./pagar-pedido.ts";

export type TonoChip = TonoEstado | "info" | "neutro";

export interface ChipEstado {
  texto: string;
  tono: TonoChip;
}

export const PALABRAS_ESTADO: Record<EstadoTrabajo, string> = {
  encolado: "Estamos armando tu kit",
  procesando: "Estamos armando tu kit",
  espera_revision: "Una persona lo está revisando",
  publicado: "Listo",
  fallido: "Hubo un problema, lo estamos revisando",
  cancelado: "Cancelaste esta solicitud",
};

export function fechaLegible(iso: string, mes: "short" | "long" = "short"): string {
  return new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: mes, year: "numeric" });
}

export function chipDeSolicitud(
  solicitud: Solicitud,
  compra: { estado: "comprado" | "pendiente_pago" | string } | null,
): ChipEstado {
  if (compra) {
    return compra.estado === "comprado"
      ? { texto: "Comprado", tono: "exito" }
      : { texto: "Pago pendiente", tono: "aviso" };
  }
  if (solicitud.tipo === "recibida") return { texto: "En revisión", tono: "aviso" };
  if (solicitud.tipo === "aprobada") return { texto: "Listo", tono: "exito" };
  switch (solicitud.estado) {
    case "publicado":
      return { texto: "Listo", tono: "exito" };
    case "encolado":
    case "procesando":
      return { texto: "Armando", tono: "info" };
    case "cancelado":
      return { texto: "Cancelada", tono: "neutro" };
    default:
      return { texto: "En revisión", tono: "aviso" };
  }
}

export const RANGO_CHIP: Record<string, number> = {
  Listo: 4,
  Comprado: 4,
  Armando: 3,
  "Pago pendiente": 2,
  "En revisión": 1,
};

export function rangoDeChip(chip: ChipEstado): number {
  return RANGO_CHIP[chip.texto] ?? 0;
}
