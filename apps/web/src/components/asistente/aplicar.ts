// Qué pide al servidor cada propuesta del asistente de /kits cuando el padre la
// confirma. El modelo solo propone: aplicar es una llamada del navegador a los
// endpoints de S3 que ya usa el renglón del kit (cambio de producto y descarte),
// con la sesión del padre, y el servidor exige que el kit sea suyo. Función pura
// para poder probarla sin React.

import type { Componente } from "./espec";

export type PropuestaAplicable = Extract<Componente, { tipo: "PropuestaCambio" | "PropuestaDescarte" }>;

export interface Aplicacion {
  url: string;
  metodo: "PUT";
  cuerpo: { sku: string } | { descartado: true };
  // El `tipo` con que se registra la decisión en /v1/nl2c/decision.
  tipo: "cambio" | "descarte";
}

export function aplicacionDePropuesta(c: PropuestaAplicable): Aplicacion | null {
  if (!c.props.aplicable) return null;
  const base =
    `/api/trabajos/${encodeURIComponent(c.props.trabajo_id)}/kits/${encodeURIComponent(c.props.perfil)}` +
    `/lineas/${encodeURIComponent(c.props.item_id)}`;
  if (c.tipo === "PropuestaCambio") {
    return { url: `${base}/producto`, metodo: "PUT", cuerpo: { sku: c.props.despues.sku }, tipo: "cambio" };
  }
  return { url: `${base}/descarte`, metodo: "PUT", cuerpo: { descartado: true }, tipo: "descarte" };
}
