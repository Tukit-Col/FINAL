// La logica pura de la ficha de un cliente (`/clientes/[id]`): que pedidos y
// casos son suyos, el resumen y su linea de actividad. Sin runner de
// componentes: se prueba con `node --test`, por eso SOLO importa tipos.
//
// Ley 1581: del menor solo viaja posicion, grado y colegio. `hijosSeguros`
// descarta cualquier campo extra (apodo, nombre) aunque el origen lo traiga.

import type { AcudienteAdmin, Caso, Pedido } from "@tukit/contrato";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function esUuid(valor: string): boolean {
  return UUID.test(valor);
}

export interface HijoSeguro {
  posicion: number;
  grado: string;
  colegio: string;
}

/** Los hijos con SOLO posicion, grado y colegio (lista blanca). */
export function hijosSeguros(hijos: AcudienteAdmin["hijos"]): HijoSeguro[] {
  return (hijos ?? []).map((h, i) => ({
    posicion: i + 1,
    grado: h.grado,
    colegio: h.colegio_nombre,
  }));
}

/** Los pedidos de un cliente, los mas recientes primero. */
export function pedidosDelCliente(pedidos: readonly Pedido[], usuarioId: string): Pedido[] {
  return pedidos
    .filter((p) => p.usuario_id === usuarioId)
    .sort((a, b) => b.creado_en.localeCompare(a.creado_en));
}

export interface ResumenCliente {
  pedidos: number;
  /** Suma de los pedidos pagados en adelante (sin cancelados ni pendientes de pago). */
  facturado: number;
  enCurso: number;
}

const FUERA_DE_LA_CUENTA = new Set(["pendiente_pago", "cancelado"]);
const CERRADOS = new Set(["entregado", "cancelado"]);

export function resumenDelCliente(pedidos: readonly Pedido[]): ResumenCliente {
  let facturado = 0;
  let enCurso = 0;
  for (const p of pedidos) {
    if (!FUERA_DE_LA_CUENTA.has(p.estado)) facturado += p.total;
    if (!FUERA_DE_LA_CUENTA.has(p.estado) && !CERRADOS.has(p.estado)) enCurso += 1;
  }
  return { pedidos: pedidos.length, facturado, enCurso };
}

/** Los trabajos (solicitudes de kit) de los que salieron sus pedidos, sin repetir. */
export function solicitudesDePedidos(pedidos: readonly Pedido[]): string[] {
  return [...new Set(pedidos.map((p) => p.trabajo_id).filter((t): t is string => !!t))];
}

export type TipoActividad = "registro" | "pedido" | "caso";

export interface Actividad {
  tipo: TipoActividad;
  cuando: string;
  titulo: string;
  /** Ruta interna a la que lleva el evento, si tiene. */
  href: string | null;
}

export function construirActividad(entrada: {
  acudiente: Pick<AcudienteAdmin, "creado_en">;
  pedidos: readonly Pedido[];
  casos: readonly Caso[];
  etiquetaEstado: (estado: Pedido["estado"]) => string;
}): Actividad[] {
  const eventos: Actividad[] = [
    { tipo: "registro", cuando: entrada.acudiente.creado_en, titulo: "Creó su cuenta", href: null },
    ...entrada.pedidos.map((p) => ({
      tipo: "pedido" as const,
      cuando: p.creado_en,
      titulo: `Pedido ${p.pedido_id.slice(0, 8)} creado (hoy: ${entrada.etiquetaEstado(p.estado)})`,
      href: `/logistica/${p.pedido_id}`,
    })),
    ...entrada.casos.map((c) => ({
      tipo: "caso" as const,
      cuando: c.abierto_en,
      titulo: `Abrió el ticket: ${c.asunto}`,
      href: `/tickets/${c.caso_id}`,
    })),
  ];
  return eventos.sort((a, b) => b.cuando.localeCompare(a.cuando));
}

/** La ruta de la ficha de un cliente. */
export function hrefCliente(usuarioId: string): string {
  return `/clientes/${usuarioId}`;
}
