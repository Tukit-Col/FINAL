// Formatos de pantalla propios de la consola.
//
// El dinero NO esta aqui: para eso existe `formatearPesos()` del contrato, y
// tener dos formateadores de pesos es como una app termina mostrando
// "$18.900" y la otra "COP 18900" para el mismo entero.

import type { ClaseLinea } from "@tukit/contrato";
import type { EstadoEtapa, EstadoTrabajo, ModoAdquisicion, TipoItem } from "@tukit/contrato";

// Zona horaria fija y no la del proceso: el servidor de Next y el navegador
// del admin no tienen por que estar en la misma, y una fecha que se pinta
// distinta en el servidor y en el cliente rompe la hidratacion.
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

// Solo el dia, para la entrega estimada: es una fecha prometida, no un instante,
// y mostrarle una hora ("00:00") al operador seria inventar precision.
const DIA = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeZone: "America/Bogota",
});

export function formatearDia(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "—";
  return DIA.format(fecha);
}

/**
 * "hace 4 min". Se calcula contra `ahora` recibido y no contra `Date.now()`
 * para que la llamada sea explicita sobre que esto solo puede pasar en un
 * Server Component: en uno de cliente el reloj del servidor y el del
 * navegador dan textos distintos.
 */
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

/** Las tres clases que son, literalmente, el trabajo pendiente del admin. */
export const CLASES_PENDIENTES: readonly ClaseLinea[] = ["hueco", "sin_match", "pendiente_revision"];

export function esPendiente(clase: ClaseLinea): boolean {
  return CLASES_PENDIENTES.includes(clase);
}

export function porcentaje(valor: number): string {
  return `${Math.round(valor * 100)} %`;
}
