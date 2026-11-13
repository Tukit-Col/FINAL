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
}

/** Versiones sin revisar agrupadas por colegio, las más cargadas primero. */
export function listasPorColegio(
  versiones: readonly VersionListaAdmin[],
  nombres: ReadonlyMap<string, string>,
  tope = 5,
): { grupos: GrupoColegio[]; total: number; colegios: number } {
  const mapa = new Map<string, GrupoColegio>();
  for (const v of versiones) {
    if (v.revisada) continue;
    const g = mapa.get(v.colegio_id) ?? {
      clave: v.colegio_id,
      nombre: nombres.get(v.colegio_id) ?? v.colegio_nombre ?? "Colegio sin identificar",
      listas: 0,
      lineas: 0,
    };
    g.listas += 1;
    g.lineas += v.items;
    mapa.set(v.colegio_id, g);
  }
  const todos = [...mapa.values()].sort(
    (a, b) => b.listas - a.listas || b.lineas - a.lineas || a.nombre.localeCompare(b.nombre, "es"),
  );
  return {
    grupos: todos.slice(0, tope),
    total: todos.reduce((t, g) => t + g.listas, 0),
    colegios: todos.length,
  };
}

export interface Actividad {
  clave: string;
  tipo: "pedido" | "ticket" | "lista";
  titulo: string;
  detalle: string;
  instante: string;
  enlace: string;
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
    items.push({
      clave: `p-${p.pedido_id}`,
      tipo: "pedido",
      titulo: `Pedido ${p.pedido_id.slice(0, 8)}`,
      detalle: `${e.etiquetaPedido(p.estado)} · ${e.dinero(p.total)}`,
      instante: p.creado_en,
      enlace: `/logistica/${p.pedido_id}`,
    });
  }
  for (const c of e.casos) {
    items.push({
      clave: `c-${c.caso_id}`,
      tipo: "ticket",
      titulo: `Ticket ${c.caso_id.slice(0, 8)}`,
      detalle: `${e.etiquetaCategoria(c.categoria)} · ${e.etiquetaPrioridad(c.prioridad)}`,
      instante: c.abierto_en,
      enlace: `/tickets/${c.caso_id}`,
    });
  }
  for (const t of e.cola?.entradas ?? []) {
    if (t.origen === "preview_onboarding") continue;
    items.push({
      clave: `l-${t.trabajo_id}`,
      tipo: "lista",
      titulo: "Lista recibida",
      detalle: e.nombreColegio(t.colegios) || "Colegio sin identificar",
      instante: t.recibido_en,
      enlace: `/trabajos/${t.trabajo_id}`,
    });
  }
  return items.sort((a, b) => ms(b.instante) - ms(a.instante)).slice(0, n);
}
