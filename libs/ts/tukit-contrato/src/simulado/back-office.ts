// Deriva las superficies ASUMIDAS de `comercio` (pedidos) y `operacion`
// (casos) a partir de lo que el simulado SÍ tiene: los trabajos del almacén.
//
// La regla de honestidad de `ARQUITECTURA.md` manda que el simulado no invente
// datos que el sistema no puede producir. Por eso un pedido nace de un trabajo
// PUBLICADO (el §Procesos hace exactamente eso: el trabajo aprobado se convierte
// en pedido y arranca la saga de pago), y un caso nace de una falla observable
// en la cola (una línea SIN_MATCH abre un MappingFailure; un HUECO_CATALOGO abre
// un StockFailure). Lo único sintético es lo que el contrato v1.0 tampoco
// atestigua todavía (la copia de la dirección de envío, la referencia de Wompi),
// y va marcado como tal — la `CintaOrigen` avisa que el origen es `simulado`.
//
// El día que `comercio` y `operacion` respondan de verdad, `cliente-http.ts` ya
// pega contra `/v1/comercio/*` y `/v1/operacion/*`: esto solo alimenta el modo
// simulado, no lo sustituye.

import type { Dinero } from "../contrato";
import type {
  EstadoPedido,
  EstadoPago,
  LineaPedido,
  Pago,
  Pedido,
  ResumenComercio,
  TableroComercio,
} from "../comercio";
import { ESTADOS_PEDIDO } from "../comercio";
import type { BandejaOperacion, Caso, ResumenOperacion } from "../operacion";
import { armarKits, resolverSolicitud } from "./armar";
import { COLEGIOS } from "./semillas";
import { listar, type RegistroTrabajo } from "./almacen";

// Hash estable de una cadena: mismo trabajo, mismo pedido, en cada lectura. No
// se usa `Math.random()` a propósito — el tablero no puede parpadear entre dos
// consultas seguidas o el operador no confía en lo que ve.
function hash(texto: string): number {
  let h = 2166136261;
  for (let i = 0; i < texto.length; i += 1) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function elegir<T>(opciones: readonly T[], semilla: number): T {
  return opciones[semilla % opciones.length] as T;
}

function nombreColegio(colegioId: string): string {
  return COLEGIOS.find((c) => c.colegio_id === colegioId)?.nombre ?? colegioId;
}

// Los estados por los que un pedido pagado puede ir pasando. `pendiente_pago`
// y `cancelado` se asignan aparte; `incidencia` la abre una falla, no el reloj.
const ESTADOS_EN_CURSO: readonly EstadoPedido[] = [
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
];

const METODOS: readonly Pago["metodo"][] = ["pse", "nequi", "tarjeta"];
const TRANSPORTADORAS = ["Servientrega", "Coordinadora", "Interrapidísimo"] as const;

function pesos(valor: number): Dinero {
  return Math.round(valor);
}

// --------------------------------------------------------------- Pedidos

function pedidoDeTrabajo(registro: RegistroTrabajo): Pedido | null {
  // Solo los trabajos publicados llegan a `comercio`: antes de la aprobación
  // humana (§7) no hay pedido que pagar.
  if (!registro.aprobado) return null;

  const resueltos = resolverSolicitud(registro.solicitud);
  const kits = armarKits(registro.solicitud, resueltos, {
    validadas: registro.validadas,
    sinCoincidencia: registro.sin_coincidencia,
    skusNoDisponibles: registro.skus_no_disponibles,
  });
  // El acudiente compra un kit; el recomendado por defecto es el Ahorrador.
  const kit = kits[0];
  if (!kit) return null;

  const lineas: LineaPedido[] = kit.lineas
    .filter((l) => l.producto_elegido && l.precio !== null && !l.informativa)
    .map((l) => ({
      sku: l.producto_elegido!.sku,
      nombre: l.producto_elegido!.nombre,
      cantidad: l.unidades_a_comprar ?? 1,
      // Precio CONGELADO en la reserva (ADR 0012): el pedido guarda lo que
      // costaba cuando se reservó, no lo que cueste hoy en el catálogo.
      precio_unitario: pesos(l.precio ?? 0),
    }));

  const total = pesos(kit.total);
  const semilla = hash(registro.trabajo_id);

  // El estado sale del hash: reparte los pedidos por el ciclo de vida sin
  // inventar una línea de tiempo que el simulado no lleva.
  const tieneHuecos = kit.lineas.some(
    (l) => l.estado_resolucion === "HUECO_CATALOGO" || l.estado_resolucion === "SIN_MATCH",
  );
  let estado: EstadoPedido;
  if (tieneHuecos) {
    // Un hueco de catálogo en el kit comprado es justo lo que abre una
    // incidencia de stock aguas abajo.
    estado = "incidencia";
  } else if (semilla % 13 === 0) {
    estado = "cancelado";
  } else {
    estado = elegir(ESTADOS_EN_CURSO, semilla);
  }

  const pagado = estado !== "pendiente_pago" && estado !== "cancelado";
  const estadoPago: EstadoPago = estado === "cancelado" ? "reembolsado" : "aprobado";
  const pago: Pago | null = pagado
    ? {
        referencia_wompi: `WMP-${semilla.toString(36).toUpperCase().slice(0, 8)}`,
        metodo: elegir(METODOS, semilla >> 3),
        estado: estadoPago,
        monto: total,
      }
    : null;

  const colegios = [...new Set(registro.solicitud.hijos.map((h) => nombreColegio(h.colegio_id)))];
  const despachado =
    estado === "despachado" || estado === "en_reparto" || estado === "entregado";

  return {
    pedido_id: `PED-${registro.trabajo_id.slice(0, 8).toUpperCase()}`,
    trabajo_id: registro.trabajo_id,
    estado,
    creado_en: new Date(registro.creado_ms).toISOString(),
    total,
    hijos: registro.solicitud.hijos.length,
    colegios,
    lineas,
    pago,
    // Copia CONGELADA de la dirección (ADR 0015). El simulado no tiene libreta
    // de direcciones, así que sintetiza una ciudad y marca lo demás como tal:
    // es lo único de esta superficie que el sistema real todavía no atestigua.
    envio: pagado
      ? {
          destinatario: `Acudiente ${registro.trabajo_id.slice(0, 4).toUpperCase()}`,
          direccion: "Dirección en el pedido (dato simulado)",
          ciudad: "Bogotá D.C.",
          transportadora: despachado ? elegir(TRANSPORTADORAS, semilla >> 5) : null,
          guia: despachado ? `${semilla % 1_000_000_000}` : null,
          entrega_estimada: null,
          entregado_en: estado === "entregado" ? new Date(registro.creado_ms).toISOString() : null,
        }
      : null,
  };
}

export function derivarTablero(): TableroComercio {
  const pedidos = listar()
    .map(pedidoDeTrabajo)
    .filter((p): p is Pedido => p !== null)
    .sort((a, b) => (a.creado_en < b.creado_en ? 1 : -1));

  const porEstado = Object.fromEntries(
    ESTADOS_PEDIDO.map((e) => [e, 0]),
  ) as Record<EstadoPedido, number>;
  let ingresos = 0;
  let entregasPendientes = 0;
  for (const pedido of pedidos) {
    porEstado[pedido.estado] += 1;
    if (pedido.pago?.estado === "aprobado") ingresos += pedido.total;
    if (
      pedido.estado === "pagado" ||
      pedido.estado === "en_preparacion" ||
      pedido.estado === "despachado" ||
      pedido.estado === "en_reparto"
    ) {
      entregasPendientes += 1;
    }
  }

  const resumen: ResumenComercio = {
    pedidos_totales: pedidos.length,
    por_estado: porEstado,
    ingresos_confirmados: pesos(ingresos),
    entregas_pendientes: entregasPendientes,
  };

  return { resumen, pedidos };
}

export function derivarPedido(pedidoId: string): Pedido | null {
  return derivarTablero().pedidos.find((p) => p.pedido_id === pedidoId) ?? null;
}

// ---------------------------------------------------------------- Casos

function casosDeTrabajo(registro: RegistroTrabajo): Caso[] {
  const resueltos = resolverSolicitud(registro.solicitud);
  const kits = armarKits(registro.solicitud, resueltos, {
    validadas: registro.validadas,
    sinCoincidencia: registro.sin_coincidencia,
    skusNoDisponibles: registro.skus_no_disponibles,
  });
  const kit = kits[0];
  if (!kit) return [];

  const casos: Caso[] = [];
  const base = new Date(registro.creado_ms).toISOString();

  // Cada línea que el sistema no pudo cerrar es una falla observable: el
  // §Procesos la nombra MappingFailure (SIN_MATCH) o StockFailure (HUECO).
  const sinMatch = kit.lineas.filter((l) => l.estado_resolucion === "SIN_MATCH");
  const huecos = kit.lineas.filter((l) => l.estado_resolucion === "HUECO_CATALOGO");

  if (sinMatch.length > 0) {
    casos.push({
      caso_id: `CAS-${registro.trabajo_id.slice(0, 6).toUpperCase()}-M`,
      origen: "sistema",
      categoria: "mapeo_lista",
      estado: registro.aprobado ? "resuelto" : "abierto",
      prioridad: "media",
      asunto: `${sinMatch.length} renglón(es) de la lista sin entender`,
      abierto_en: base,
      vence_en: null,
      trabajo_id: registro.trabajo_id,
      pedido_id: null,
      asignado_a: null,
    });
  }

  if (huecos.length > 0) {
    casos.push({
      caso_id: `CAS-${registro.trabajo_id.slice(0, 6).toUpperCase()}-S`,
      origen: "sistema",
      categoria: "stock",
      estado: "en_gestion",
      prioridad: "media",
      asunto: `${huecos.length} concepto(s) sin producto en catálogo`,
      abierto_en: base,
      vence_en: null,
      trabajo_id: registro.trabajo_id,
      pedido_id: registro.aprobado
        ? `PED-${registro.trabajo_id.slice(0, 8).toUpperCase()}`
        : null,
      asignado_a: null,
    });
  }

  return casos;
}

export function derivarBandeja(): BandejaOperacion {
  const casos = listar()
    .flatMap(casosDeTrabajo)
    .sort((a, b) => (a.abierto_en < b.abierto_en ? 1 : -1));

  const activos = casos.filter((c) => c.estado !== "resuelto" && c.estado !== "cerrado");
  const resumen: ResumenOperacion = {
    abiertos: activos.length,
    urgentes: activos.filter((c) => c.prioridad === "urgente").length,
    vencen_hoy: activos.filter((c) => c.vence_en !== null).length,
    resueltos_semana: casos.filter((c) => c.estado === "resuelto").length,
  };

  return { resumen, casos };
}

export function derivarCaso(casoId: string): Caso | null {
  return derivarBandeja().casos.find((c) => c.caso_id === casoId) ?? null;
}
