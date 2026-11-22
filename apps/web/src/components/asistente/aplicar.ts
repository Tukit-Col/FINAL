import type { Componente } from "./espec";

export type PropuestaAplicable = Extract<Componente, { tipo: "PropuestaCambio" | "PropuestaDescarte" }>;

export interface Aplicacion {
  url: string;
  metodo: "PUT";
  cuerpo: { sku: string } | { descartado: true };
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

export function pendientesDelTurno(
  componentes: readonly Componente[],
  turno: number,
  estados: Readonly<Record<string, "pendiente" | "aplicada" | "rechazada">>,
): { clave: string; componente: PropuestaAplicable }[] {
  const salida: { clave: string; componente: PropuestaAplicable }[] = [];
  componentes.forEach((c, i) => {
    if (c.tipo !== "PropuestaCambio" && c.tipo !== "PropuestaDescarte") return;
    const clave = `${turno}-${i}`;
    if (!c.props.aplicable || (estados[clave] ?? "pendiente") !== "pendiente") return;
    salida.push({ clave, componente: c });
  });
  return salida;
}

export function renglonesPorDecidir(
  turnos: readonly (readonly Componente[] | null)[],
  estados: Readonly<Record<string, "pendiente" | "aplicada" | "rechazada">>,
): string[] {
  const vistos = new Set<string>();
  turnos.forEach((componentes, t) => {
    if (!componentes) return;
    for (const { componente } of pendientesDelTurno(componentes, t, estados)) vistos.add(componente.props.item_id);
  });
  return [...vistos];
}
