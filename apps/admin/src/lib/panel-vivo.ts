// Lo que el panel agrega a las tarjetas de acción: flujo de pedidos, tickets por
// estado, listas por verificar por colegio y actividad reciente. Todo se deriva
// de lo que ya devuelven pedidos(), casos() y cola()/listasAdmin(): sin
// endpoints nuevos. Puro (solo tipos del contrato) para `node --test`.
// Ley 1581: solo conteos e ids; nunca nombre ni apodo de un menor, y del ticket
// no se muestra el asunto (texto libre del acudiente).

import type {
  Caso,
  ColaAdmin,
  EstadoCaso,
  EstadoPedido,
  Pedido,
  ResumenComercio,
  VersionListaAdmin,
} from "@tukit/contrato";
import type { TonoEstado } from "./graficos";

export const ETAPAS_FLUJO: readonly EstadoPedido[] = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
];

export interface EtapaFlujo {
  estado: EstadoPedido;
  cantidad: number;
  enlace: string;
}

export function flujoDePedidos(resumen: ResumenComercio): {
  etapas: EtapaFlujo[];
  incidencia: EtapaFlujo;
  cancelado: EtapaFlujo;
} {
  const de = (estado: EstadoPedido): EtapaFlujo => ({
    estado,
    cantidad: resumen.por_estado?.[estado] ?? 0,
    enlace: `/logistica?estado=${estado}`,
  });
  return {
    etapas: ETAPAS_FLUJO.map(de),
    incidencia: de("incidencia"),
    cancelado: de("cancelado"),
  };
}

export interface FilaTickets {
  clave: string;
  cantidad: number;
  enlace: string;
  /** El plazo ya venció: va en rojo. */
  critico?: boolean;
}

const ESTADOS_ACTIVOS: readonly EstadoCaso[] = ["abierto", "en_gestion", "esperando_tercero"];

/** Activos por estado + los cortes de SLA. `vencen_hoy` no tiene filtro propio en /tickets. */
export function ticketsPorEstado(
  casos: readonly Caso[],
  resumen: { urgentes: number; vencen_hoy: number; vencidos?: number },
): { estados: FilaTickets[]; sla: FilaTickets[] } {
  const estados = ESTADOS_ACTIVOS.map((e) => ({
    clave: e,
    cantidad: casos.filter((c) => c.estado === e).length,
    enlace: `/tickets?estado=${e}`,
  }));
  const sla: FilaTickets[] = [
    {
      clave: "vencidos",
      cantidad: resumen.vencidos ?? 0,
      enlace: "/tickets?vencidos=1",
      critico: true,
    },
    { clave: "vencen_hoy", cantidad: resumen.vencen_hoy, enlace: "/tickets" },
    { clave: "urgentes", cantidad: resumen.urgentes, enlace: "/tickets?prioridad=urgente" },
  ];
  return { estados, sla };
}

export interface GrupoColegio {
  clave: string;
  nombre: string;
  listas: number;
  lineas: number;
  /** Versiones de este colegio con un acudiente esperando su kit. */
  esperando: number;
}

export interface ListasPanel {
  grupos: GrupoColegio[];
  /** Lo que no cupo en el tope, sumado en una sola barra final. */
  otros: { colegios: number; listas: number } | null;
  total: number;
  colegios: number;
  /** Versiones (no colegios) con acudiente esperando. */
  esperando: number;
  /** Conteo por grado, en el orden pedagogico recibido; los desconocidos al final. */
  porGrado: { grado: string; listas: number }[];
  /** Todas las barras visibles valen lo mismo: pintarlas finas, no como ranking. */
  uniforme: boolean;
}

/**
 * Versiones sin revisar agrupadas por colegio. Orden: primero los colegios con
 * acudiente esperando (es lo que dispara un kit), luego los mas cargados. Lo que
 * pasa del tope se suma en `otros`. `ordenGrados` es la lista canonica (se pasa
 * desde la pagina para que este modulo siga sin dependencias de runtime).
 */
export function listasPorColegio(
  versiones: readonly VersionListaAdmin[],
  nombres: ReadonlyMap<string, string>,
  tope = 5,
  ordenGrados: readonly string[] = [],
): ListasPanel {
  const mapa = new Map<string, GrupoColegio>();
  const grados = new Map<string, number>();
  let esperando = 0;
  for (const v of versiones) {
    if (v.revisada) continue;
    const g = mapa.get(v.colegio_id) ?? {
      clave: v.colegio_id,
      nombre: nombres.get(v.colegio_id) ?? v.colegio_nombre ?? "Colegio sin identificar",
      listas: 0,
      lineas: 0,
      esperando: 0,
    };
    g.listas += 1;
    g.lineas += v.items;
    if (v.tiene_contacto) {
      g.esperando += 1;
      esperando += 1;
    }
    mapa.set(v.colegio_id, g);
    const grado = v.grado || "Sin grado";
    grados.set(grado, (grados.get(grado) ?? 0) + 1);
  }
  const todos = [...mapa.values()].sort(
    (a, b) =>
      b.esperando - a.esperando ||
      b.listas - a.listas ||
      b.lineas - a.lineas ||
      a.nombre.localeCompare(b.nombre, "es"),
  );
  const grupos = todos.slice(0, tope);
  const resto = todos.slice(tope);
  const posicion = (g: string) => {
    const i = ordenGrados.indexOf(g);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };
  return {
    grupos,
    otros: resto.length
      ? { colegios: resto.length, listas: resto.reduce((t, g) => t + g.listas, 0) }
      : null,
    total: todos.reduce((t, g) => t + g.listas, 0),
    colegios: todos.length,
    esperando,
    porGrado: [...grados.entries()]
      .map(([grado, listas]) => ({ grado, listas }))
      .sort((a, b) => posicion(a.grado) - posicion(b.grado) || a.grado.localeCompare(b.grado, "es")),
    uniforme: grupos.length > 1 && grupos.every((g) => g.listas === grupos[0].listas),
  };
}

export type { TonoEstado };

export const TONO_PEDIDO: Record<EstadoPedido, TonoEstado> = {
  pendiente_pago: "aviso",
  pagado: "exito",
  en_preparacion: "aviso",
  despachado: "info",
  en_reparto: "info",
  entregado: "exito",
  incidencia: "peligro",
  cancelado: "neutro",
};

const TONO_PRIORIDAD: Record<Caso["prioridad"], TonoEstado> = {
  urgente: "peligro",
  alta: "peligro",
  media: "aviso",
  baja: "neutro",
};

export interface Actividad {
  clave: string;
  tipo: "pedido" | "ticket" | "lista";
  titulo: string;
  /** Texto plano completo (estado · monto, o categoria · prioridad). */
  detalle: string;
  instante: string;
  enlace: string;
  /** Lo que va en la insignia de color. */
  estado: string;
  tono: TonoEstado;
  /** Lo secundario que no es estado: la categoria del ticket o el colegio. */
  nota?: string;
  /** Solo pedidos: el total ya formateado, para destacarlo a la derecha. */
  monto?: string;
}

export interface EntradaActividad {
  pedidos: readonly Pedido[];
  casos: readonly Caso[];
  cola: ColaAdmin | null;
  etiquetaPedido: (e: EstadoPedido) => string;
  etiquetaCategoria: (c: Caso["categoria"]) => string;
  etiquetaPrioridad: (p: Caso["prioridad"]) => string;
  dinero: (v: number) => string;
  nombreColegio: (ids: string[]) => string;
}

function ms(iso: string): number {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/** Los últimos `n` eventos mezclando pedidos, tickets y listas. */
export function actividadReciente(e: EntradaActividad, n = 8): Actividad[] {
  const items: Actividad[] = [];
  for (const p of e.pedidos) {
    const estado = e.etiquetaPedido(p.estado);
    const monto = e.dinero(p.total);
    items.push({
      clave: `p-${p.pedido_id}`,
      tipo: "pedido",
      titulo: `Pedido ${p.pedido_id.slice(0, 8)}`,
      detalle: `${estado} · ${monto}`,
      instante: p.creado_en,
      enlace: `/logistica/${p.pedido_id}`,
      estado,
      tono: TONO_PEDIDO[p.estado] ?? "neutro",
      monto,
    });
  }
  for (const c of e.casos) {
    const categoria = e.etiquetaCategoria(c.categoria);
    const prioridad = e.etiquetaPrioridad(c.prioridad);
    items.push({
      clave: `c-${c.caso_id}`,
      tipo: "ticket",
      titulo: `Ticket ${c.caso_id.slice(0, 8)}`,
      detalle: `${categoria} · ${prioridad}`,
      instante: c.abierto_en,
      enlace: `/tickets/${c.caso_id}`,
      estado: prioridad,
      tono: TONO_PRIORIDAD[c.prioridad] ?? "neutro",
      nota: categoria,
    });
  }
  for (const t of e.cola?.entradas ?? []) {
    if (t.origen === "preview_onboarding") continue;
    const colegio = e.nombreColegio(t.colegios) || "Colegio sin identificar";
    items.push({
      clave: `l-${t.trabajo_id}`,
      tipo: "lista",
      titulo: "Lista recibida",
      detalle: colegio,
      instante: t.recibido_en,
      enlace: `/trabajos/${t.trabajo_id}`,
      estado: "Por revisar",
      tono: "info",
      nota: colegio,
    });
  }
  return items.sort((a, b) => ms(b.instante) - ms(a.instante)).slice(0, n);
}

// Dia calendario en Bogota (YYYY-MM-DD): el servidor puede correr en UTC y un
// pedido de las 8 p. m. no debe caer en "mañana".
const DIA_BOGOTA = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Bogota",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const DIA_SEMANA = new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", weekday: "short" });
const DIA_LARGO = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  weekday: "long",
  day: "numeric",
  month: "long",
});

export function diaBogota(instante: number): string {
  return DIA_BOGOTA.format(new Date(instante));
}

/** Dias calendario entre dos claves YYYY-MM-DD (b - a). */
function diasEntre(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
}

/** "Hoy", "Ayer", "Hace N días" (N <= 7) o la fecha larga. */
export function tituloDia(dia: string, hoy: string): string {
  const d = diasEntre(dia, hoy);
  if (d <= 0) return "Hoy";
  if (d === 1) return "Ayer";
  if (d <= 7) return `Hace ${d} días`;
  const largo = DIA_LARGO.format(new Date(`${dia}T12:00:00-05:00`));
  return largo.charAt(0).toUpperCase() + largo.slice(1);
}

export interface DiaActividad {
  clave: string;
  titulo: string;
  items: Actividad[];
}

/** Agrupa la actividad (ya ordenada) por dia de Bogota, conservando el orden. */
export function agruparPorDia(items: readonly Actividad[], ahora: number): DiaActividad[] {
  const hoy = diaBogota(ahora);
  const grupos: DiaActividad[] = [];
  for (const a of items) {
    const t = ms(a.instante);
    const clave = t ? diaBogota(t) : "sin-fecha";
    let g = grupos.at(-1);
    if (!g || g.clave !== clave) {
      g = { clave, titulo: t ? tituloDia(clave, hoy) : "Sin fecha", items: [] };
      grupos.push(g);
    }
    g.items.push(a);
  }
  return grupos;
}

export interface ColumnaDia {
  clave: string;
  /** "lun", "mar"…; el ultimo es "Hoy". */
  etiqueta: string;
  /** Para lectores de pantalla: "lunes 9 de noviembre". */
  etiquetaLarga: string;
  valor: number;
}

/** Pedidos creados en cada uno de los ultimos `dias` dias (el ultimo es hoy). */
export function pedidosPorDia(
  pedidos: readonly Pick<Pedido, "creado_en">[],
  ahora: number,
  dias = 7,
): ColumnaDia[] {
  const cuenta = new Map<string, number>();
  for (const p of pedidos) {
    const t = ms(p.creado_en);
    if (!t) continue;
    const d = diaBogota(t);
    cuenta.set(d, (cuenta.get(d) ?? 0) + 1);
  }
  const columnas: ColumnaDia[] = [];
  for (let i = dias - 1; i >= 0; i--) {
    const instante = ahora - i * 86_400_000;
    const clave = diaBogota(instante);
    const fecha = new Date(instante);
    columnas.push({
      clave,
      etiqueta: i === 0 ? "Hoy" : DIA_SEMANA.format(fecha).replace(".", ""),
      etiquetaLarga: DIA_LARGO.format(fecha),
      valor: cuenta.get(clave) ?? 0,
    });
  }
  return columnas;
}
