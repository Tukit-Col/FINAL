// La logica pura de la bandeja de tickets: filtros desde la URL, orden y
// etiquetas. Sin runner de componentes: se prueba con `node --test`, por eso
// SOLO importa tipos del contrato.

import type { Caso, CategoriaCaso, EstadoCaso } from "@tukit/contrato";

// El operador piensa en abierto / en curso / resuelto; los dos estados extra del
// backend (esperando a un tercero, cerrado) se muestran con su nombre.
export const ETIQUETA_ESTADO_TICKET: Record<EstadoCaso, string> = {
  abierto: "Abierto",
  en_gestion: "En curso",
  esperando_tercero: "Esperando a un tercero",
  resuelto: "Resuelto",
  cerrado: "Cerrado",
};

export const ESTADOS_TICKET: readonly EstadoCaso[] = [
  "abierto",
  "en_gestion",
  "esperando_tercero",
  "resuelto",
  "cerrado",
];

export interface FiltrosTickets {
  estado: EstadoCaso | "";
  categoria: CategoriaCaso | "";
  // Prefijo del id del caso o texto en el asunto.
  q: string;
}

type Parametros = Record<string, string | string[] | undefined>;

const CATEGORIAS: readonly string[] = [
  "pago",
  "stock",
  "entrega",
  "mapeo_lista",
  "autenticacion",
  "peticion",
  "queja",
  "reclamo",
  "sugerencia",
];

function primero(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

/** Los filtros de la URL, saneados: un valor desconocido se ignora en vez de
 *  dejar la bandeja vacia sin explicacion. */
export function leerFiltrosTickets(p: Parametros): FiltrosTickets {
  const estado = primero(p.estado);
  const categoria = primero(p.categoria);
  return {
    estado: (ESTADOS_TICKET as readonly string[]).includes(estado) ? (estado as EstadoCaso) : "",
    categoria: CATEGORIAS.includes(categoria) ? (categoria as CategoriaCaso) : "",
    q: primero(p.q),
  };
}

export function hayFiltrosTickets(f: FiltrosTickets): boolean {
  return Object.values(f).some((v) => v !== "");
}

export function filtrarCasos(casos: readonly Caso[], f: FiltrosTickets): Caso[] {
  const q = f.q.toLowerCase();
  return casos.filter((c) => {
    if (f.estado && c.estado !== f.estado) return false;
    if (f.categoria && c.categoria !== f.categoria) return false;
    if (q && !c.caso_id.toLowerCase().startsWith(q) && !c.asunto.toLowerCase().includes(q)) return false;
    return true;
  });
}

/** Vencido: sigue activo y su termino (Ley 1755 o SLA de negocio) ya paso. */
export function estaVencido(caso: Caso, ahora: number): boolean {
  if (caso.estado === "resuelto" || caso.estado === "cerrado" || !caso.vence_en) return false;
  const limite = new Date(caso.vence_en).getTime();
  return !Number.isNaN(limite) && limite < ahora;
}

/** Los estados a los que se puede pasar desde el actual. Espejo de
 *  `TRANSICIONES_CASO` del contrato, que importa `admin.ts` con runtime; aqui se
 *  recibe la tabla para no importar valores en el modulo probado. */
export function destinosPosibles(
  actual: EstadoCaso,
  tabla: Record<EstadoCaso, readonly EstadoCaso[]>,
): readonly EstadoCaso[] {
  return tabla[actual] ?? [];
}

/** Cuanto falta (o paso) del termino, en palabras para la fila. */
export function textoVencimiento(caso: Caso, ahora: number): string | null {
  if (!caso.vence_en || caso.estado === "resuelto" || caso.estado === "cerrado") return null;
  const limite = new Date(caso.vence_en).getTime();
  if (Number.isNaN(limite)) return null;
  const horas = Math.round((limite - ahora) / 3_600_000);
  if (horas < 0) {
    const dias = Math.floor(-horas / 24);
    return dias >= 1 ? `vencido hace ${dias} d` : `vencido hace ${-horas} h`;
  }
  if (horas < 48) return `vence en ${horas} h`;
  return `vence en ${Math.round(horas / 24)} d`;
}
