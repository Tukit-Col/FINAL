import type { Pedido } from "@tukit/contrato";
import type { Punto, ResultadoGeo } from "./geocodificador";

const PENDIENTES = new Set(["pagado", "en_preparacion", "despachado", "en_reparto"]);

export function esEntregaPendiente(pedido: Pedido): boolean {
  return PENDIENTES.has(pedido.estado) && pedido.envio !== null;
}

export interface EntregaPendiente {
  pedido_id: string;
  estado: Pedido["estado"];
  destinatario: string;
  direccion: string;
  ciudad: string;
  departamento: string | null;
  colegios: string[];
  hijos: number;
  punto: ResultadoGeo;
}

export interface GrupoColegio {
  colegio: string;
  entregas: EntregaPendiente[];
  hijos: number;
  conMarcador: number;
  sinMarcador: number;
}

export const SIN_COLEGIO = "Sin colegio";

export function agruparPorColegio(entregas: readonly EntregaPendiente[]): GrupoColegio[] {
  const grupos = new Map<string, GrupoColegio>();
  for (const e of entregas) {
    const nombres = e.colegios.length > 0 ? e.colegios : [SIN_COLEGIO];
    for (const colegio of nombres) {
      let g = grupos.get(colegio);
      if (!g) {
        g = { colegio, entregas: [], hijos: 0, conMarcador: 0, sinMarcador: 0 };
        grupos.set(colegio, g);
      }
      g.entregas.push(e);
      g.hijos += e.hijos;
      if (typeof e.punto === "object" && e.punto !== null) g.conMarcador += 1;
      else g.sinMarcador += 1;
    }
  }
  return [...grupos.values()].sort(
    (a, b) => b.entregas.length - a.entregas.length || a.colegio.localeCompare(b.colegio, "es"),
  );
}

export interface Marcador {
  punto: Punto;
  colegio: string;
  entregas: EntregaPendiente[];
}

export function marcadoresDe(grupos: readonly GrupoColegio[]): Marcador[] {
  const salida: Marcador[] = [];
  for (const g of grupos) {
    const porSitio = new Map<string, Marcador>();
    for (const e of g.entregas) {
      if (typeof e.punto !== "object" || e.punto === null) continue;
      const clave = `${e.punto.lat.toFixed(4)},${e.punto.lon.toFixed(4)}`;
      const existente = porSitio.get(clave);
      if (existente) existente.entregas.push(e);
      else porSitio.set(clave, { punto: e.punto, colegio: g.colegio, entregas: [e] });
    }
    salida.push(...porSitio.values());
  }
  return salida;
}

export interface HijoSalon {
  colegio_nombre: string;
  grado: string;
}

export interface FilaSalon {
  colegio: string;
  grado: string;
  hijos: number;
}

export function contarPorSalon(hijos: readonly HijoSalon[]): FilaSalon[] {
  const cuenta = new Map<string, FilaSalon>();
  for (const h of hijos) {
    const clave = `${h.colegio_nombre}|${h.grado}`;
    const fila = cuenta.get(clave) ?? { colegio: h.colegio_nombre, grado: h.grado, hijos: 0 };
    fila.hijos += 1;
    cuenta.set(clave, fila);
  }
  return [...cuenta.values()].sort(
    (a, b) =>
      a.colegio.localeCompare(b.colegio, "es") || a.grado.localeCompare(b.grado, "es", { numeric: true }),
  );
}
