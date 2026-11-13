// La logica pura de la bandeja de tickets: filtros desde la URL, orden y
// etiquetas. Sin runner de componentes: se prueba con `node --test`, por eso
// SOLO importa tipos del contrato.

import type { Caso, CategoriaCaso, EstadoCaso, Prioridad } from "@tukit/contrato";

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
  prioridad: Prioridad | "";
  // "ninguno" = sin dueño; "mios" = asignados a quien mira la bandeja.
  asignado: "" | "ninguno" | "mios";
  // Solo activos con el termino ya pasado.
  vencidos: boolean;
  pagina: number;
}

const PRIORIDADES: readonly string[] = ["urgente", "alta", "media", "baja"];

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
    prioridad: PRIORIDADES.includes(primero(p.prioridad)) ? (primero(p.prioridad) as Prioridad) : "",
    asignado: ["ninguno", "mios"].includes(primero(p.asignado)) ? (primero(p.asignado) as "ninguno" | "mios") : "",
    vencidos: ["1", "true"].includes(primero(p.vencidos)),
    pagina: paginaValida(primero(p.pagina)),
  };
}

function paginaValida(texto: string): number {
  const n = Number(texto);
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

/** Si hay algun filtro puesto (la pagina no cuenta: es navegacion, no filtro). */
export function hayFiltrosTickets(f: FiltrosTickets): boolean {
  return f.estado !== "" || f.categoria !== "" || f.q !== "" || f.prioridad !== "" || f.asignado !== "" || f.vencidos;
}

type FiltrosBasicos = Pick<FiltrosTickets, "estado" | "categoria" | "q"> & Partial<FiltrosTickets>;

export function filtrarCasos(
  casos: readonly Caso[],
  f: FiltrosBasicos,
  ahora: number = Date.now(),
  yo: string | null = null,
): Caso[] {
  const q = f.q.toLowerCase();
  return casos.filter((c) => {
    if (f.estado && c.estado !== f.estado) return false;
    if (f.categoria && c.categoria !== f.categoria) return false;
    if (f.prioridad && c.prioridad !== f.prioridad) return false;
    if (f.asignado === "ninguno" && c.asignado_a !== null) return false;
    if (f.asignado === "mios" && (yo === null || c.asignado_a !== yo)) return false;
    if (f.vencidos && !estaVencido(c, ahora)) return false;
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

/** El instante actual, en una funcion aparte: la pagina es un Server Component
 *  (se pinta una vez por peticion) y la regla de pureza de React no distingue. */
export function instanteActual(): number {
  return Date.now();
}

// ------------------------------------------------------- Fase 4: bandeja en tarjetas

export const TAMANO_PAGINA = 20;

export interface Pagina<T> {
  items: T[];
  pagina: number;
  total: number;
  paginas: number;
}

/** Una pagina de `items`. Una pagina fuera de rango se acota; sin items hay 1 pagina vacia. */
export function paginar<T>(items: readonly T[], pagina: number, tamano: number = TAMANO_PAGINA): Pagina<T> {
  const paginas = Math.max(1, Math.ceil(items.length / tamano));
  const actual = Math.min(Math.max(1, Math.trunc(pagina) || 1), paginas);
  const desde = (actual - 1) * tamano;
  return { items: items.slice(desde, desde + tamano), pagina: actual, total: items.length, paginas };
}

export type TonoSla = "vencido" | "hoy" | "ok" | "sin";

/** El chip de SLA de una tarjeta: texto y tono. Sin termino (o ticket cerrado), `sin`. */
export function etiquetaSla(caso: Caso, ahora: number): { texto: string; tono: TonoSla } {
  const texto = textoVencimiento(caso, ahora);
  if (texto === null) return { texto: "", tono: "sin" };
  if (estaVencido(caso, ahora)) return { texto, tono: "vencido" };
  const limite = new Date(caso.vence_en as string).getTime();
  return { texto, tono: limite - ahora <= 24 * 3_600_000 ? "hoy" : "ok" };
}

export function claseDePrioridad(p: Prioridad): string {
  return `prioridad_${p}`;
}

/** Los enlaces de paginacion conservan los demas filtros. */
export function hrefTickets(f: FiltrosTickets, cambios: Partial<FiltrosTickets>): string {
  const todo = { ...f, ...cambios };
  const parametros = new URLSearchParams();
  if (todo.q) parametros.set("q", todo.q);
  if (todo.estado) parametros.set("estado", todo.estado);
  if (todo.categoria) parametros.set("categoria", todo.categoria);
  if (todo.prioridad) parametros.set("prioridad", todo.prioridad);
  if (todo.asignado) parametros.set("asignado", todo.asignado);
  if (todo.vencidos) parametros.set("vencidos", "1");
  if (todo.pagina > 1) parametros.set("pagina", String(todo.pagina));
  const cola = parametros.toString();
  return cola ? `/tickets?${cola}` : "/tickets";
}

// ------------------------------------------------------- Fase 4: asignar y soltar

export function textoAsignacion(asignadoA: string | null, yo: string | null): string {
  if (asignadoA === null) return "Sin asignar";
  return asignadoA === yo ? "Asignado a ti" : "Asignado a otra persona";
}

/** Soltar lo ve quien tiene el ticket o un admin (el servicio lo exige igual). */
export function puedeSoltar(asignadoA: string | null, yo: string | null, esAdmin: boolean): boolean {
  if (asignadoA === null) return false;
  return esAdmin || asignadoA === yo;
}
