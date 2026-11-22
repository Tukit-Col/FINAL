import type { Dinero } from "./contrato";

export class DineroInvalido extends Error {}

export function comoDinero(valor: unknown, donde: string): Dinero {
  if (typeof valor !== "number" || !Number.isInteger(valor)) {
    throw new DineroInvalido(
      `${donde}: el dinero va en pesos enteros y llego ${JSON.stringify(valor)}.`,
    );
  }
  return valor;
}

export function comoDineroONulo(valor: unknown, donde: string): Dinero | null {
  return valor === null || valor === undefined ? null : comoDinero(valor, donde);
}

const FORMATO_COP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

export function formatearPesos(valor: Dinero | null | undefined): string {
  if (valor === null || valor === undefined) return "Sin precio";
  return FORMATO_COP.format(valor);
}

export function sumarPesos(valores: readonly (Dinero | null | undefined)[]): Dinero {
  return valores.reduce<number>((total, v) => total + (typeof v === "number" ? v : 0), 0);
}

export function formatearTamano(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
