import type { Caso, CategoriaCaso, EstadoCaso, Prioridad } from "@tukit/contrato";

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
  q: string;
  prioridad: Prioridad | "";
  asignado: "" | "ninguno" | "mios";
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

export function estaVencido(caso: Caso, ahora: number): boolean {
  if (caso.estado === "resuelto" || caso.estado === "cerrado" || !caso.vence_en) return false;
  const limite = new Date(caso.vence_en).getTime();
  return !Number.isNaN(limite) && limite < ahora;
}

export function destinosPosibles(
  actual: EstadoCaso,
  tabla: Record<EstadoCaso, readonly EstadoCaso[]>,
): readonly EstadoCaso[] {
  return tabla[actual] ?? [];
}

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

export function instanteActual(): number {
  return Date.now();
}

export const TAMANO_PAGINA = 20;

export interface Pagina<T> {
  items: T[];
  pagina: number;
  total: number;
  paginas: number;
}

export function paginar<T>(items: readonly T[], pagina: number, tamano: number = TAMANO_PAGINA): Pagina<T> {
  const paginas = Math.max(1, Math.ceil(items.length / tamano));
  const actual = Math.min(Math.max(1, Math.trunc(pagina) || 1), paginas);
  const desde = (actual - 1) * tamano;
  return { items: items.slice(desde, desde + tamano), pagina: actual, total: items.length, paginas };
}

export type TonoSla = "vencido" | "hoy" | "ok" | "sin";

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

export function textoAsignacion(asignadoA: string | null, yo: string | null): string {
  if (asignadoA === null) return "Sin asignar";
  return asignadoA === yo ? "Asignado a ti" : "Asignado a otra persona";
}

export function puedeSoltar(asignadoA: string | null, yo: string | null, esAdmin: boolean): boolean {
  if (asignadoA === null) return false;
  return esAdmin || asignadoA === yo;
}
