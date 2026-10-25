// La logica pura de la pantalla de logistica: filtros, busqueda por codigo
// corto, dia de Bogota, acciones por estado y la fecha estimada con zona.
//
// Correr:  node --test test/logistica.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { Pedido } from "@tukit/contrato";
import {
  accionesDisponibles,
  claveFiltros,
  colegiosDisponibles,
  diaBogota,
  fechaEstimadaIso,
  filtrarPedidos,
  hayFiltros,
  leerFiltros,
  motivoDeAcceso,
  motivoDeFallo,
  ordenarPorPrioridad,
} from "../src/lib/logistica.ts";

function pedido(extra: Partial<Pedido>): Pedido {
  return {
    pedido_id: "abcd1234-0000-4000-8000-000000000000",
    trabajo_id: null,
    estado: "pagado",
    creado_en: "2026-10-03T15:00:00Z",
    total: 9000,
    hijos: 1,
    colegios: ["Colegio San Jose"],
    lineas: [],
    pago: null,
    envio: null,
    ...extra,
  };
}

const PEDIDOS = [
  pedido({}),
  pedido({
    pedido_id: "ffff0000-0000-4000-8000-000000000000",
    estado: "incidencia",
    colegios: ["Gimnasio Moderno"],
    // 9 p. m. de Bogota del 1: en UTC ya es el 2.
    creado_en: "2026-10-02T02:00:00Z",
  }),
];

const SIN_FILTROS = leerFiltros({});

test("leerFiltros ignora un estado o una fecha invalidos", () => {
  const f = leerFiltros({ estado: "volando", desde: "ayer", hasta: "2026-10-03", q: ["  ABCD ", "x"] });
  assert.deepEqual(f, { q: "ABCD", estado: "", colegio: "", desde: "", hasta: "2026-10-03" });
  assert.equal(hayFiltros(SIN_FILTROS), false);
  assert.equal(hayFiltros(f), true);
});

test("la busqueda es por prefijo del id, sin distinguir mayusculas", () => {
  assert.equal(filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, q: "ABCD1234" }).length, 1);
  assert.equal(filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, q: "1234" }).length, 0);
});

test("filtra por estado y por colegio", () => {
  assert.equal(filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, estado: "incidencia" })[0]!.estado, "incidencia");
  assert.deepEqual(
    filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, colegio: "Colegio San Jose" }).map((p) => p.pedido_id[0]),
    ["a"],
  );
});

test("el rango de fechas usa el dia de Bogota", () => {
  assert.equal(diaBogota("2026-10-02T02:00:00Z"), "2026-10-01");
  const delPrimero = filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, desde: "2026-10-01", hasta: "2026-10-01" });
  assert.deepEqual(delPrimero.map((p) => p.estado), ["incidencia"]);
  assert.equal(filtrarPedidos(PEDIDOS, { ...SIN_FILTROS, desde: "2026-10-04" }).length, 0);
});

test("colegios unicos y ordenados; la incidencia va primero", () => {
  assert.deepEqual(colegiosDisponibles(PEDIDOS), ["Colegio San Jose", "Gimnasio Moderno"]);
  assert.equal(ordenarPorPrioridad(PEDIDOS)[0]!.estado, "incidencia");
});

test("claveFiltros cambia con cualquier filtro", () => {
  assert.notEqual(claveFiltros(SIN_FILTROS), claveFiltros({ ...SIN_FILTROS, colegio: "x" }));
});

test("acciones por estado espejan la matriz de comercio", () => {
  const destinos = (e: Parameters<typeof accionesDisponibles>[0]) =>
    accionesDisponibles(e).map((a) => a.destino);
  assert.deepEqual(destinos("pagado"), ["en_preparacion", "incidencia"]);
  assert.deepEqual(destinos("en_preparacion"), ["despachado", "incidencia"]);
  assert.deepEqual(destinos("despachado"), ["en_reparto", "incidencia"]);
  assert.deepEqual(destinos("en_reparto"), ["entregado", "incidencia"]);
  assert.deepEqual(destinos("incidencia"), ["en_preparacion", "cancelado"]);
  for (const cerrado of ["pendiente_pago", "entregado", "cancelado"] as const) {
    assert.deepEqual(destinos(cerrado), []);
  }
  assert.equal(accionesDisponibles("en_preparacion")[0]!.forma, "despachar");
  assert.equal(accionesDisponibles("incidencia")[1]!.forma, "cancelar");
});

test("la fecha estimada va con la zona de Bogota", () => {
  assert.equal(fechaEstimadaIso("2026-10-05"), "2026-10-05T00:00:00-05:00");
  assert.equal(fechaEstimadaIso(""), null);
  assert.equal(fechaEstimadaIso("5/10/2026"), null);
});

test("motivoDeFallo distingue sesion, rol y caida", () => {
  assert.equal(motivoDeFallo(401), "sesion_expirada");
  assert.equal(motivoDeFallo(403), "sin_rol");
  assert.equal(motivoDeFallo(503), "servicio_caido");
});

test("un 429 es el limite de tasa, no un servicio caido ni una sesion vencida", () => {
  assert.equal(motivoDeFallo(429), "limite");
});

test("motivoDeAcceso: un error de sesion, rol o limite se pinta como aviso, lo demas sube", () => {
  assert.equal(motivoDeAcceso({ estado: 401 }), "sesion_expirada");
  assert.equal(motivoDeAcceso({ estado: 403 }), "sin_rol");
  assert.equal(motivoDeAcceso({ estado: 429 }), "limite");
  // Un 404 o una caida no son de acceso: la pagina decide (notFound o error).
  assert.equal(motivoDeAcceso({ estado: 404 }), null);
  assert.equal(motivoDeAcceso({ estado: 503 }), null);
  assert.equal(motivoDeAcceso(new Error("red")), null);
  assert.equal(motivoDeAcceso(undefined), null);
});
