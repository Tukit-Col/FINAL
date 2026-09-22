// Todo el dinero de Tukit es un entero de pesos colombianos (§1.4).
//
// El alias `Dinero` nombra la unidad pero no la impone: `18900` y `189.00`
// son los dos `number`. Estas funciones son el unico sitio donde un valor
// entra o sale, y la de arriba es la que convierte un error silencioso de
// unidad en uno ruidoso. El defecto que previene es concreto: la base guarda
// `precio_oferta.valor_centavos`, o sea que el factor 100 existe de verdad en
// el sistema y en algun borde hay que dividirlo.

import type { Dinero } from "./contrato";

export class DineroInvalido extends Error {}

/** Valida que un valor recibido de la red sea dinero del contrato. */
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

/** `18900` -> `"$ 18.900"`. */
export function formatearPesos(valor: Dinero | null | undefined): string {
  if (valor === null || valor === undefined) return "Sin precio";
  return FORMATO_COP.format(valor);
}

/** Suma sin salirse de los enteros. */
export function sumarPesos(valores: readonly (Dinero | null | undefined)[]): Dinero {
  return valores.reduce<number>((total, v) => total + (typeof v === "number" ? v : 0), 0);
}

export function formatearTamano(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
