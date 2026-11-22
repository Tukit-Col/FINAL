import type { AlertaPedido, EstadoPedido, Pedido } from "@tukit/contrato";

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
  q: string;
  estado: EstadoPedido | "";
  colegio: string;
  desde: string;
  hasta: string;
  alerta: AlertaPedido | "";
  vista: VistaLogistica;
}

type ParametrosBusqueda = Record<string, string | string[] | undefined>;

const DIA = /^\d{4}-\d{2}-\d{2}$/;

function primero(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";
}

const ALERTAS: readonly AlertaPedido[] = ["pagado_sin_avanzar", "pago_atascado", "incidencia_abierta"];

function esAlerta(valor: string): valor is AlertaPedido {
  return (ALERTAS as readonly string[]).includes(valor);
}

function esEstado(valor: string): valor is EstadoPedido {
  return Object.hasOwn(PRIORIDAD_ESTADO, valor);
}

export function leerFiltros(parametros: ParametrosBusqueda): FiltrosLogistica {
  const estado = primero(parametros.estado);
  const desde = primero(parametros.desde);
  const hasta = primero(parametros.hasta);
  const alerta = primero(parametros.alerta);
  const vista = primero(parametros.vista);
  return {
    q: primero(parametros.q),
    estado: esEstado(estado) ? estado : "",
    colegio: primero(parametros.colegio),
    desde: DIA.test(desde) ? desde : "",
    hasta: DIA.test(hasta) ? hasta : "",
    alerta: esAlerta(alerta) ? alerta : "",
    vista: esVista(vista) ? vista : VISTA_POR_DEFECTO,
  };
}

export function hayFiltros(filtros: FiltrosLogistica): boolean {
  return [filtros.q, filtros.estado, filtros.colegio, filtros.desde, filtros.hasta, filtros.alerta].some(
    (v) => v !== "",
  );
}

export function claveFiltros(filtros: FiltrosLogistica): string {
  return [filtros.q, filtros.estado, filtros.colegio, filtros.desde, filtros.hasta, filtros.alerta].join("|");
}

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

export const COLEGIO_NINGUNO = "sin-colegio";

export function filtrarPedidos(pedidos: readonly Pedido[], filtros: FiltrosLogistica): Pedido[] {
  const q = filtros.q.toLowerCase();
  return pedidos.filter((pedido) => {
    if (q && !pedido.pedido_id.toLowerCase().startsWith(q)) return false;
    if (filtros.estado && pedido.estado !== filtros.estado) return false;
    if (filtros.colegio === COLEGIO_NINGUNO) {
      if (pedido.colegios.length > 0) return false;
    } else if (filtros.colegio && !pedido.colegios.includes(filtros.colegio)) return false;
    if (filtros.alerta && !(pedido.alertas ?? []).includes(filtros.alerta)) return false;
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

export function fechaEstimadaIso(dia: string): string | null {
  return DIA.test(dia) ? `${dia}T00:00:00-05:00` : null;
}

export type FormaAccion = "simple" | "despachar" | "incidencia" | "cancelar";

export interface AccionLogistica {
  destino: EstadoPedido;
  etiqueta: string;
  forma: FormaAccion;
}

const PREPARAR: AccionLogistica = { destino: "en_preparacion", etiqueta: "Pasar a preparación", forma: "simple" };
const INCIDENCIA: AccionLogistica = { destino: "incidencia", etiqueta: "Reportar incidencia", forma: "incidencia" };

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

export type MotivoAcceso = "sin_sesion" | "sesion_expirada" | "sin_rol" | "servicio_caido" | "limite";

export function motivoDeFallo(estado: number): MotivoAcceso {
  if (estado === 401) return "sesion_expirada";
  if (estado === 403) return "sin_rol";
  if (estado === 429) return "limite";
  return "servicio_caido";
}

export function motivoDeAcceso(causa: unknown): MotivoAcceso | null {
  const estado = (causa as { estado?: unknown } | null | undefined)?.estado;
  if (estado === 401 || estado === 403 || estado === 429) return motivoDeFallo(estado);
  return null;
}

export interface MotivoSinAcciones {
  titulo: string;
  detalle: string;
  accion?: "reconciliar";
}

export function motivoSinAcciones(estado: EstadoPedido): MotivoSinAcciones | null {
  if (accionesDisponibles(estado).length > 0) return null;
  if (estado === "pendiente_pago") {
    return {
      titulo: "Esperando el pago",
      detalle:
        "El pedido se mueve cuando Wompi confirma el pago. Si el acudiente ya pagó y no avanza, pregúntale a Wompi: " +
        "si aprobó, el pedido pasa a Pagado. Si nadie paga en 24 h, el pedido vence solo.",
      accion: "reconciliar",
    };
  }
  if (estado === "entregado") {
    return { titulo: "Entregado: sin pasos pendientes", detalle: "El pedido llegó a su destino y ya no se mueve." };
  }
  return {
    titulo: "Cancelado",
    detalle: "El pedido está cancelado y su pago quedó marcado para reembolso si estaba aprobado.",
  };
}

export type ClaseDeFallo = "sesion" | "rol" | "conflicto" | "pasarela" | "otro";

export function claseDeFallo(estado: number): ClaseDeFallo {
  if (estado === 401) return "sesion";
  if (estado === 403) return "rol";
  if (estado === 409) return "conflicto";
  if (estado === 502) return "pasarela";
  return "otro";
}

export function rutaSinActivar(estado: number): boolean {
  return estado === 404 || estado === 405;
}

export type ResultadoReconciliacion = "pagado" | "en_curso" | "libre";

export function etiquetaResultadoReconciliacion(r: ResultadoReconciliacion): string {
  switch (r) {
    case "pagado":
      return "El pago estaba aprobado: el pedido pasó a Pagado";
    case "en_curso":
      return "El pago sigue en curso en Wompi";
    case "libre":
      return "No hay un pago aprobado: el pedido sigue sin pagar";
  }
}

const RANGO_FORMA: Record<FormaAccion, number> = { simple: 0, despachar: 0, incidencia: 1, cancelar: 2 };

export function destinosParaSelector(estado: EstadoPedido): AccionLogistica[] {
  return [...accionesDisponibles(estado)].sort((a, b) => RANGO_FORMA[a.forma] - RANGO_FORMA[b.forma]);
}

const DESTINO_DE_LOTE: Partial<Record<EstadoPedido, "en_preparacion" | "en_reparto" | "entregado">> = {
  pagado: "en_preparacion",
  despachado: "en_reparto",
  en_reparto: "entregado",
};

export function destinoComunDeLote(pedidos: readonly Pick<Pedido, "estado">[]): EstadoPedido | null {
  if (pedidos.length === 0) return null;
  const destinos = new Set(pedidos.map((p) => DESTINO_DE_LOTE[p.estado] ?? null));
  if (destinos.size !== 1) return null;
  return [...destinos][0] ?? null;
}

export function resumenDeLote(r: {
  avanzados: readonly unknown[];
  fallidos: readonly unknown[];
}): string {
  const n = r.avanzados.length;
  return `${n} ${n === 1 ? "avanzado" : "avanzados"}, ${r.fallidos.length} con problema`;
}

export const ETIQUETA_PASO_ACUDIENTE: Record<string, string> = {
  creado: "Pedido creado",
  pagado: "Pago confirmado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
};

export function textoAviso(aviso: string | null): string {
  switch (aviso) {
    case "pedido_en_preparacion":
      return "Le avisamos que estamos preparando su kit.";
    case "pedido_cancelado":
      return "Le avisamos que se canceló el pedido y si hay reembolso.";
    case "pedido_despachado":
      return "Le avisamos que su pedido salió despachado.";
    case "pedido_en_reparto":
      return "Le avisamos que su pedido va en reparto.";
    case "pedido_entregado":
      return "Le avisamos que su pedido fue entregado.";
    case "incidencia":
      return "Le avisamos que hubo un inconveniente con la entrega.";
    default:
      return "No se le envía aviso: el contacto lo haces tú.";
  }
}

export function hrefConAlerta(filtros: FiltrosLogistica, alerta: AlertaPedido | ""): string {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries({ ...filtros, alerta })) {
    if (clave === "vista" && valor === VISTA_POR_DEFECTO) continue;
    if (valor) parametros.set(clave, valor);
  }
  const cola = parametros.toString();
  return cola ? `/logistica?${cola}` : "/logistica";
}

export function codigoCorto(pedidoId: string): string {
  return pedidoId.slice(0, 8);
}

export type VistaLogistica = "tablero" | "tabla";

export const VISTA_POR_DEFECTO: VistaLogistica = "tablero";

function esVista(valor: string): valor is VistaLogistica {
  return valor === "tablero" || valor === "tabla";
}

export const COLUMNAS_FLUJO: readonly EstadoPedido[] = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
];

export const CARRIL_APARTE: readonly EstadoPedido[] = ["incidencia", "cancelado"];

export const ESTADOS_LIMITADOS: readonly EstadoPedido[] = ["entregado", "cancelado"];
export const LIMITE_CERRADOS = 5;
export const LIMITE_ABIERTAS = 8;

export interface ColumnaTablero {
  estado: EstadoPedido;
  total: number;
  pedidos: Pedido[];
  ocultos: number;
}

export function fechaDeEtapa(pedido: Pedido): string {
  if (pedido.estado === "entregado" && pedido.envio?.entregado_en) return pedido.envio.entregado_en;
  return pedido.creado_en;
}

function instante(iso: string): number {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

export function agruparPorEtapa(
  pedidos: readonly Pedido[],
  estados: readonly EstadoPedido[],
  limite: number = LIMITE_CERRADOS,
  limiteAbiertas: number = LIMITE_ABIERTAS,
): ColumnaTablero[] {
  return estados.map((estado) => {
    const deLaEtapa = pedidos.filter((p) => p.estado === estado);
    const cerrada = ESTADOS_LIMITADOS.includes(estado);
    const ordenados = [...deLaEtapa].sort((a, b) => {
      if (cerrada) return instante(fechaDeEtapa(b)) - instante(fechaDeEtapa(a));
      const alerta = Number((b.alertas ?? []).length > 0) - Number((a.alertas ?? []).length > 0);
      return alerta !== 0 ? alerta : instante(fechaDeEtapa(a)) - instante(fechaDeEtapa(b));
    });
    const visibles = ordenados.slice(0, Math.max(0, cerrada ? limite : limiteAbiertas));
    return { estado, total: deLaEtapa.length, pedidos: visibles, ocultos: deLaEtapa.length - visibles.length };
  });
}

export function articulosDePedido(pedido: Pick<Pedido, "lineas">): number {
  return pedido.lineas.reduce((suma, linea) => suma + linea.cantidad, 0);
}

export interface AccionDeTarjeta {
  accion: AccionLogistica;
  directa: boolean;
}

export function accionDeTarjeta(estado: EstadoPedido): AccionDeTarjeta | null {
  if (estado === "incidencia") return null;
  const accion = accionesDisponibles(estado).find((a) => a.forma === "simple" || a.forma === "despachar");
  if (!accion) return null;
  return { accion, directa: accion.forma === "simple" };
}

export function hrefConVista(filtros: FiltrosLogistica, vista: VistaLogistica): string {
  return hrefConAlerta({ ...filtros, vista }, filtros.alerta);
}

export function hrefEtapaEnTabla(filtros: FiltrosLogistica, estado: EstadoPedido): string {
  return hrefConAlerta({ ...filtros, estado, vista: "tabla" }, filtros.alerta);
}

export function hrefColegioEnTabla(colegioId: string | null): string {
  return `/logistica?${new URLSearchParams({ vista: "tabla", colegio: colegioId ?? COLEGIO_NINGUNO })}`;
}
