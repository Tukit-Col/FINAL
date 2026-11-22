import { test } from "node:test";
import assert from "node:assert/strict";
import type { Pedido } from "@tukit/contrato";
import {
  claveFiltros,
  COLEGIO_NINGUNO,
  colegiosDisponibles,
  diaBogota,
  filtrarPedidos,
  hayFiltros,
  hrefColegioEnTabla,
  hrefConAlerta,
  hrefConVista,
  hrefEtapaEnTabla,
  leerFiltros,
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
    creado_en: "2026-10-02T02:00:00Z",
  }),
];

const SIN_FILTROS = leerFiltros({});

test("leerFiltros ignora un estado o una fecha invalidos", () => {
  const f = leerFiltros({ estado: "volando", desde: "ayer", hasta: "2026-10-03", q: ["  ABCD ", "x"] });
  assert.deepEqual(f, { q: "ABCD", estado: "", colegio: "", desde: "", hasta: "2026-10-03", alerta: "", vista: "tablero" });
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

test("filtro por alerta se conserva, se sanea y filtra", () => {
  assert.equal(leerFiltros({ alerta: "pago_atascado" }).alerta, "pago_atascado");
  assert.equal(leerFiltros({ alerta: "x" }).alerta, "");
  const a = pedido({ pedido_id: "a1", alertas: ["pago_atascado"] });
  const b = pedido({ pedido_id: "b1" });
  const f = leerFiltros({ alerta: "pago_atascado" });
  assert.deepEqual(filtrarPedidos([a, b], f).map((p) => p.pedido_id), ["a1"]);
  assert.equal(hayFiltros(f), true);
});

test("hrefConAlerta conserva los otros filtros", () => {
  const f = leerFiltros({ estado: "pagado", alerta: "pago_atascado" });
  assert.equal(hrefConAlerta(f, "pagado_sin_avanzar"), "/logistica?estado=pagado&alerta=pagado_sin_avanzar");
  assert.equal(hrefConAlerta(leerFiltros({}), ""), "/logistica");
});

test("vista: tablero por defecto, se sanea y no cuenta como filtro", () => {
  assert.equal(leerFiltros({}).vista, "tablero");
  assert.equal(leerFiltros({ vista: "tabla" }).vista, "tabla");
  assert.equal(leerFiltros({ vista: "<script>" }).vista, "tablero");
  assert.equal(hayFiltros(leerFiltros({ vista: "tabla" })), false);
});

test("hrefConVista conserva los filtros y no escribe la vista por defecto", () => {
  const f = leerFiltros({ alerta: "pago_atascado", vista: "tabla" });
  assert.equal(hrefConVista(f, "tablero"), "/logistica?alerta=pago_atascado");
  assert.equal(hrefConVista(leerFiltros({}), "tabla"), "/logistica?vista=tabla");
  assert.equal(hrefConAlerta(f, ""), "/logistica?vista=tabla");
  assert.equal(hrefEtapaEnTabla(leerFiltros({}), "entregado"), "/logistica?estado=entregado&vista=tabla");
});

test("colegio 'sin-colegio' filtra pedidos sin colegio y hrefColegioEnTabla lleva a la tabla", () => {
  const f = leerFiltros({ colegio: COLEGIO_NINGUNO });
  const r = filtrarPedidos([pedido({ pedido_id: "a", colegios: [] }), pedido({ pedido_id: "b", colegios: ["c1"] })], f);
  assert.deepEqual(r.map((p) => p.pedido_id), ["a"]);
  assert.equal(hrefColegioEnTabla(null), "/logistica?vista=tabla&colegio=sin-colegio");
  assert.equal(hrefColegioEnTabla("c1"), "/logistica?vista=tabla&colegio=c1");
});
