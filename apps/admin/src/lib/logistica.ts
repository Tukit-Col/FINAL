// La logica pura de la pantalla de logistica: filtros, orden, acciones por
// estado y el formato de la fecha estimada.
//
// Vive aparte de las paginas para probarse con `node --test` (sin runner de
// componentes) y por eso SOLO importa tipos del contrato: el runtime de Node no
// resuelve los imports sin extension de `@tukit/contrato`.

import type { EstadoPedido, Pedido } from "@tukit/contrato";

// Orden operativo: primero lo que hay que atender (incidencias), luego lo que
// hay que mover (en curso) y al final lo cerrado. Es un `Record` exhaustivo: un
// estado nuevo en el contrato no compila hasta tener su lugar aqui, y sus
// llaves son ademas la lista de estados validos para el filtro.
export const PRIORIDAD_ESTADO: Record<EstadoPedido, number> = {
  incidencia: 0,
  pagado: 1,
  en_preparacion: 2,
  despachado: 3,
  en_reparto: 4,
  pendiente_pago: 5,
  entregado: 6,
  cancelado: 7,
};

export function ordenarPorPrioridad(pedidos: readonly Pedido[]): Pedido[] {
  return [...pedidos].sort((a, b) => PRIORIDAD_ESTADO[a.estado] - PRIORIDAD_ESTADO[b.estado]);
}

export interface FiltrosLogistica {
  // Prefijo del id del pedido: sirve el codigo corto de 8 que ve el papa.
  q: string;
  estado: EstadoPedido | "";
  colegio: string;
  // Dias de Bogota, `YYYY-MM-DD`, sobre `creado_en`. Vacio = sin limite.
  desde: string;
  hasta: string;
}

type ParametrosBusqueda = Record<string, string | string[] | undefined>;

const DIA = /^\d{4}-\d{2}-\d{2}$/;

function primero(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";
}

function esEstado(valor: string): valor is EstadoPedido {
  return Object.hasOwn(PRIORIDAD_ESTADO, valor);
}

/** Los filtros de la URL, saneados: un estado o una fecha que no son validos
 *  se ignoran en vez de dejar la tabla vacia sin explicacion. */
export function leerFiltros(parametros: ParametrosBusqueda): FiltrosLogistica {
  const estado = primero(parametros.estado);
  const desde = primero(parametros.desde);
  const hasta = primero(parametros.hasta);
  return {
    q: primero(parametros.q),
    estado: esEstado(estado) ? estado : "",
    colegio: primero(parametros.colegio),
    desde: DIA.test(desde) ? desde : "",
    hasta: DIA.test(hasta) ? hasta : "",
  };
}

export function hayFiltros(filtros: FiltrosLogistica): boolean {
  return Object.values(filtros).some((v) => v !== "");
}

/** Una clave estable de los filtros, para remontar el formulario al cambiarlos. */
export function claveFiltros(filtros: FiltrosLogistica): string {
  return [filtros.q, filtros.estado, filtros.colegio, filtros.desde, filtros.hasta].join("|");
}

// `en-CA` formatea como `YYYY-MM-DD`, que se compara como texto. Zona fija y no
// la del proceso: un pedido de las 9 p. m. de Bogota es de ese dia, aunque en
// UTC ya sea el siguiente.
const DIA_BOGOTA = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Bogota",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function diaBogota(iso: string): string {
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? "" : DIA_BOGOTA.format(fecha);
}

export function filtrarPedidos(pedidos: readonly Pedido[], filtros: FiltrosLogistica): Pedido[] {
  const q = filtros.q.toLowerCase();
  return pedidos.filter((pedido) => {
    if (q && !pedido.pedido_id.toLowerCase().startsWith(q)) return false;
    if (filtros.estado && pedido.estado !== filtros.estado) return false;
    if (filtros.colegio && !pedido.colegios.includes(filtros.colegio)) return false;
    if (filtros.desde || filtros.hasta) {
      const dia = diaBogota(pedido.creado_en);
      if (filtros.desde && dia < filtros.desde) return false;
      if (filtros.hasta && dia > filtros.hasta) return false;
    }
    return true;
  });
}

export function colegiosDisponibles(pedidos: readonly Pedido[]): string[] {
  return [...new Set(pedidos.flatMap((p) => p.colegios))].sort((a, b) => a.localeCompare(b, "es"));
}

/** El dia elegido en el formulario como medianoche de Bogota CON zona: comercio
 *  rechaza una fecha sin zona (se correria al guardarla). Bogota no tiene horario
 *  de verano, asi que `-05:00` es fijo. */
export function fechaEstimadaIso(dia: string): string | null {
  return DIA.test(dia) ? `${dia}T00:00:00-05:00` : null;
}

// Que pide cada accion antes de enviarse. `simple` va directo; las demas abren
// su formulario o su confirmacion.
export type FormaAccion = "simple" | "despachar" | "incidencia" | "cancelar";

export interface AccionLogistica {
  destino: EstadoPedido;
  etiqueta: string;
  forma: FormaAccion;
}

const PREPARAR: AccionLogistica = { destino: "en_preparacion", etiqueta: "Pasar a preparación", forma: "simple" };
const INCIDENCIA: AccionLogistica = { destino: "incidencia", etiqueta: "Reportar incidencia", forma: "incidencia" };

// Espejo de `AVANCES_DE_LOGISTICA` en `comercio/dominio/despacho.py`: un boton
// por transicion que el back-office puede hacer. Si se desalinean, comercio
// responde 409 y el boton muestra su mensaje; no se abre nada por aqui.
const ACCIONES: Partial<Record<EstadoPedido, readonly AccionLogistica[]>> = {
  pagado: [PREPARAR, INCIDENCIA],
  en_preparacion: [{ destino: "despachado", etiqueta: "Despachar", forma: "despachar" }, INCIDENCIA],
  despachado: [{ destino: "en_reparto", etiqueta: "Salió a reparto", forma: "simple" }, INCIDENCIA],
  en_reparto: [{ destino: "entregado", etiqueta: "Marcar entregado", forma: "simple" }, INCIDENCIA],
  incidencia: [
    { destino: "en_preparacion", etiqueta: "Reprogramar", forma: "simple" },
    { destino: "cancelado", etiqueta: "Cancelar pedido", forma: "cancelar" },
  ],
};

export function accionesDisponibles(estado: EstadoPedido): readonly AccionLogistica[] {
  return ACCIONES[estado] ?? [];
}

// Por que la pantalla no puede mostrar logistica. Cada motivo tiene su texto
// en `AvisoAcceso`.
export type MotivoAcceso = "sin_sesion" | "sesion_expirada" | "sin_rol" | "servicio_caido" | "limite";

/** El motivo a partir del HTTP con que fallo la lectura. Un 429 es el limite de
 *  tasa (ADR 0047): la sesion sigue viva y los servicios arriba, solo hay que
 *  esperar. */
export function motivoDeFallo(estado: number): MotivoAcceso {
  if (estado === 401) return "sesion_expirada";
  if (estado === 403) return "sin_rol";
  if (estado === 429) return "limite";
  return "servicio_caido";
}
