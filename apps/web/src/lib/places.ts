// Carga perezosa de Google Places (New) para el campo de dirección del checkout
// (ADR 0039). La llave es de servidor: la lee `kits/[trabajo_id]/page.tsx` y
// llega por props, nunca por `NEXT_PUBLIC_`. Cualquier fallo —sin red, llave
// inválida, API no habilitada— devuelve `null` y el checkout sigue con campos
// manuales: Maps jamás bloquea el pago.

import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

declare global {
  interface Window {
    // Google lo llama cuando rechaza la llave (referrer, API o facturación).
    gm_authFailure?: () => void;
  }
}

let promesa: Promise<google.maps.PlacesLibrary | null> | null = null;
let llaveRechazada = false;
const avisos = new Set<() => void>();

// Para que el campo deje de pedir sugerencias en cuanto Google rechaza la llave:
// el rechazo llega después de cargar, en la primera llamada.
export function alRechazarLlave(aviso: () => void): () => void {
  avisos.add(aviso);
  return () => avisos.delete(aviso);
}

export function llaveFueRechazada(): boolean {
  return llaveRechazada;
}

// Google rechazó la llave: por `gm_authFailure`, o porque una llamada volvió con
// un error de permisos (la API no está habilitada). Desde ahí, todo manual.
export function rechazarLlave(): void {
  if (llaveRechazada) return;
  llaveRechazada = true;
  for (const aviso of avisos) aviso();
}

export function cargarPlaces(llave: string): Promise<google.maps.PlacesLibrary | null> {
  if (llaveRechazada) return Promise.resolve(null);
  if (!promesa) {
    window.gm_authFailure = rechazarLlave;
    try {
      setOptions({ key: llave, v: "weekly", language: "es", region: "CO" });
      promesa = importLibrary("places").catch(() => null);
    } catch {
      promesa = Promise.resolve(null);
    }
  }
  return promesa;
}
