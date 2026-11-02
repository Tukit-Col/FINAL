// Linea de tiempo, enmascarado de datos personales y totales del detalle de
// pedido, mas el consolidado del mapa y los filtros de tickets.
//
// Correr:  node --test test/pedido-admin.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { Caso, Pedido, PedidoAdmin } from "@tukit/contrato";
import {
  construirLineaDeTiempo,
  enmascararCorreo,
  enmascararTelefono,
  formatearDiaIso,
  lineasConSubtotal,
  totalDescuadrado,
} from "../src/lib/pedido-admin.ts";
import {
  agruparPorColegio,
  contarPorSalon,
  esEntregaPendiente,
  marcadoresDe,
  type EntregaPendiente,
} from "../src/lib/consolidado.ts";
import {
  estaVencido,
  filtrarCasos,
  hayFiltrosTickets,
  leerFiltrosTickets,
  textoVencimiento,
} from "../src/lib/tickets.ts";

function pedido(extra: Partial<PedidoAdmin> = {}): PedidoAdmin {
  return {
    pedido_id: "abcd1234-0000-4000-8000-000000000000",
    usuario_id: "u1",
    trabajo_id: null,
    estado: "en_preparacion",
    creado_en: "2026-10-30T14:00:00Z",
    total: 13500,
    hijos: 1,
    colegios: ["Colegio San José"],
    lineas: [
      { sku: "A", nombre: "Cuaderno", cantidad: 2, precio_unitario: 4500 },
      { sku: "B", nombre: "Lapiz", cantidad: 1, precio_unitario: 4500 },
    ],
    pago: {
      referencia_wompi: "ref",
      metodo: "pse",
      estado: "aprobado",
      monto: 13500,
      transaccion_wompi: "tx-1",
      actualizado_en: "2026-10-30T14:05:00Z",
    },
    envio: null,
    historial: [
      {
        estado_desde: "pagado",
        estado_hacia: "en_preparacion",
        actor_id: "op",
        actor_correo: "op@tukit.co",
        nota: null,
        tipo_incidencia: null,
        creado_en: "2026-10-30T16:00:00Z",
      },
    ],
    devoluciones: [],
    ...extra,
  };
}

test("enmascara correo y telefono dejando lo justo para reconocerlos", () => {
  assert.equal(enmascararCorreo("maria@correo.com"), "m***@correo.com");
  assert.equal(enmascararCorreo(null), "—");
  assert.equal(enmascararCorreo("sin-arroba"), "***");
  assert.equal(enmascararTelefono("310 999 8877"), "••• ••• 8877");
  assert.equal(enmascararTelefono("12"), "•••");
});

test("la linea de tiempo marca hechos, actual y pendientes con quien y cuando", () => {
  const pasos = construirLineaDeTiempo(pedido());
  assert.deepEqual(
    pasos.map((p) => p.situacion),
    ["hecho", "hecho", "actual", "pendiente", "pendiente", "pendiente"],
  );
  assert.equal(pasos[1].quien, "Wompi");
  assert.equal(pasos[1].cuando, "2026-10-30T14:05:00Z");
  assert.equal(pasos[2].quien, "op@tukit.co");
  assert.equal(pasos[3].cuando, null);
});

test("un reprogramar no reescribe la fecha original de un paso", () => {
  const p = pedido({
    historial: [
      { estado_desde: "pagado", estado_hacia: "en_preparacion", actor_id: "a", actor_correo: "a@t.co", nota: null, tipo_incidencia: null, creado_en: "2026-10-30T16:00:00Z" },
      { estado_desde: "en_preparacion", estado_hacia: "incidencia", actor_id: "a", actor_correo: "a@t.co", nota: null, tipo_incidencia: "otro", creado_en: "2026-10-31T10:00:00Z" },
      { estado_desde: "incidencia", estado_hacia: "en_preparacion", actor_id: "b", actor_correo: "b@t.co", nota: null, tipo_incidencia: null, creado_en: "2026-11-01T10:00:00Z" },
    ],
  });
  const paso = construirLineaDeTiempo(p)[2];
  assert.equal(paso.cuando, "2026-10-30T16:00:00Z");
  assert.equal(paso.quien, "a@t.co");
});

test("pendiente de pago: solo 'creado' esta hecho y sin pago no hay paso de pago", () => {
  const pasos = construirLineaDeTiempo(pedido({ estado: "pendiente_pago", pago: null, historial: [] }));
  assert.equal(pasos[0].situacion, "actual");
  assert.equal(pasos[1].cuando, null);
});

test("subtotales por linea y descuadre del total", () => {
  const p = pedido();
  assert.deepEqual(lineasConSubtotal(p).map((l) => l.subtotal), [9000, 4500]);
  assert.equal(totalDescuadrado(p), false);
  assert.equal(totalDescuadrado(pedido({ total: 1 })), true);
});

test("un plazo YYYY-MM-DD se pinta sin correrse de dia", () => {
  assert.match(formatearDiaIso("2026-11-09"), /9/);
  assert.equal(formatearDiaIso(null), "—");
  assert.equal(formatearDiaIso("mañana"), "—");
});

// --------------------------------------------------------------- consolidado

function entrega(id: string, colegios: string[], punto: EntregaPendiente["punto"], hijos = 1): EntregaPendiente {
  return { pedido_id: id, estado: "pagado", destinatario: "X", direccion: "d", ciudad: "Bogotá", departamento: null, colegios, hijos, punto };
}

test("solo los pedidos pagados y sin entregar con envio son entregas pendientes", () => {
  const base = { pedido_id: "p", usuario_id: "u", trabajo_id: null, creado_en: "x", total: 1, hijos: 1, colegios: [], lineas: [], pago: null } as const;
  const envio = { destinatario: "a", direccion: "b", ciudad: "c" } as Pedido["envio"];
  assert.equal(esEntregaPendiente({ ...base, estado: "en_reparto", envio }), true);
  assert.equal(esEntregaPendiente({ ...base, estado: "entregado", envio }), false);
  assert.equal(esEntregaPendiente({ ...base, estado: "pendiente_pago", envio }), false);
  assert.equal(esEntregaPendiente({ ...base, estado: "pagado", envio: null }), false);
});

test("agrupa por colegio, cuenta con y sin marcador y ordena por volumen", () => {
  const p = { lat: 4.6, lon: -74.1 };
  const grupos = agruparPorColegio([
    entrega("1", ["Gimnasio"], p),
    entrega("2", ["San José"], null),
    entrega("3", ["San José"], "pendiente", 2),
    entrega("4", [], p),
  ]);
  assert.equal(grupos[0].colegio, "San José");
  assert.deepEqual([grupos[0].entregas.length, grupos[0].hijos, grupos[0].conMarcador, grupos[0].sinMarcador], [2, 3, 0, 2]);
  assert.ok(grupos.some((g) => g.colegio === "Sin colegio"));
});

test("pedidos al mismo sitio se apilan en un marcador; sin punto no hay marcador", () => {
  const p = { lat: 4.60971, lon: -74.08171 };
  const grupos = agruparPorColegio([entrega("1", ["A"], p), entrega("2", ["A"], { lat: 4.60972, lon: -74.08172 }), entrega("3", ["A"], null)]);
  const m = marcadoresDe(grupos);
  assert.equal(m.length, 1);
  assert.equal(m[0].entregas.length, 2);
});

test("cuenta hijos por colegio y salon con grados en orden natural", () => {
  const filas = contarPorSalon([
    { colegio_nombre: "A", grado: "10" },
    { colegio_nombre: "A", grado: "2" },
    { colegio_nombre: "A", grado: "2" },
  ]);
  assert.deepEqual(filas.map((f) => [f.grado, f.hijos]), [["2", 2], ["10", 1]]);
});

// ------------------------------------------------------------------- tickets

function caso(extra: Partial<Caso>): Caso {
  return {
    caso_id: "11111111-0000-4000-8000-000000000000",
    origen: "acudiente",
    categoria: "reclamo",
    estado: "abierto",
    prioridad: "alta",
    asunto: "Llegó incompleto",
    abierto_en: "2026-10-30T00:00:00Z",
    vence_en: "2026-11-14T00:00:00Z",
    trabajo_id: null,
    pedido_id: null,
    asignado_a: null,
    ...extra,
  };
}

test("los filtros de tickets ignoran valores desconocidos", () => {
  const f = leerFiltrosTickets({ estado: "volando", categoria: "pago", q: [" hola "] });
  assert.deepEqual(f, { estado: "", categoria: "pago", q: "hola" });
  assert.equal(hayFiltrosTickets(f), true);
});

test("filtra por estado, categoria y texto (prefijo de id o asunto)", () => {
  const casos = [caso({}), caso({ caso_id: "22222222-0", estado: "resuelto", categoria: "pago", asunto: "Cobro doble" })];
  assert.equal(filtrarCasos(casos, { estado: "resuelto", categoria: "", q: "" }).length, 1);
  assert.equal(filtrarCasos(casos, { estado: "", categoria: "", q: "2222" }).length, 1);
  assert.equal(filtrarCasos(casos, { estado: "", categoria: "", q: "cobro" }).length, 1);
});

test("vencimiento: solo cuenta en tickets activos", () => {
  const ahora = new Date("2026-11-20T00:00:00Z").getTime();
  assert.equal(estaVencido(caso({}), ahora), true);
  assert.equal(estaVencido(caso({ estado: "resuelto" }), ahora), false);
  assert.match(textoVencimiento(caso({}), ahora) ?? "", /vencido hace 6 d/);
  assert.equal(textoVencimiento(caso({ estado: "cerrado" }), ahora), null);
});
