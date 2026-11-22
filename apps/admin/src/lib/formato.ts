import type { ClaseLinea } from "@tukit/contrato";
import type { EstadoEtapa, EstadoTrabajo, ModoAdquisicion, TipoItem } from "@tukit/contrato";

const FECHA = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

export function formatearFecha(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return FECHA.format(fecha);
}

const DIA = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeZone: "America/Bogota",
});

export function formatearDia(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return DIA.format(fecha);
}

export function haceCuanto(iso: string, ahora: number): string {
  const fecha = new Date(iso).getTime();
  if (Number.isNaN(fecha)) return "—";
  const segundos = Math.max(0, Math.round((ahora - fecha) / 1000));
  if (segundos < 60) return "hace menos de un minuto";
  const minutos = Math.round(segundos / 60);
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  return `hace ${Math.round(horas / 24)} d`;
}

export const TITULO_ESTADO_TRABAJO: Record<EstadoTrabajo, string> = {
  encolado: "En cola",
  procesando: "Procesando",
  espera_revision: "Espera revisión",
  publicado: "Publicado",
  fallido: "Fallido",
  cancelado: "Cancelado por el acudiente",
};

export const TITULO_ESTADO_ETAPA: Record<EstadoEtapa, string> = {
  pendiente: "pendiente",
  en_curso: "en curso",
  ok: "ok",
  incompleta: "incompleta",
  fallida: "fallida",
};

export const TITULO_TIPO: Record<TipoItem, string> = {
  util: "útil",
  texto: "texto escolar",
  libro_libre: "libro libre",
  licencia_digital: "licencia digital",
  no_comprar: "no comprar",
  diferido: "diferido",
  uniforme: "uniforme",
  otro: "otro",
};

export const TITULO_MODO: Record<ModoAdquisicion, string> = {
  mercado_abierto: "mercado abierto",
  libro_libre: "cualquier editorial",
  venta_directa_editorial: "venta directa de la editorial",
  edicion_exclusiva: "edición exclusiva del colegio",
  plataforma: "plataforma con link de pago",
  diferido: "lo pide el colegio después",
};

export const CLASES_PENDIENTES: readonly ClaseLinea[] = ["hueco", "sin_match", "pendiente_revision"];

export function esPendiente(clase: ClaseLinea): boolean {
  return CLASES_PENDIENTES.includes(clase);
}

export function porcentaje(valor: number): string {
  return `${Math.round(valor * 100)} %`;
}
