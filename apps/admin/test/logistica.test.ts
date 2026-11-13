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

// ---------------------------------------------------------- Fase 4
import {
  claseDeFallo,
  destinoComunDeLote,
  destinosParaSelector,
  etiquetaResultadoReconciliacion,
  motivoSinAcciones,
  resumenDeLote,
} from "../src/lib/logistica.ts";

test("motivoSinAcciones: pendiente_pago ofrece reconciliar y menciona las 24 h", () => {
  const m = motivoSinAcciones("pendiente_pago");
  assert.equal(m?.accion, "reconciliar");
  assert.match(m?.detalle ?? "", /24 h/);
  assert.equal(motivoSinAcciones("entregado")?.accion, undefined);
  assert.equal(motivoSinAcciones("cancelado")?.accion, undefined);
  assert.equal(motivoSinAcciones("pagado"), null);
});

test("claseDeFallo", () => {
  assert.equal(claseDeFallo(401), "sesion");
  assert.equal(claseDeFallo(403), "rol");
  assert.equal(claseDeFallo(409), "conflicto");
  assert.equal(claseDeFallo(502), "pasarela");
  assert.equal(claseDeFallo(500), "otro");
});

test("etiquetaResultadoReconciliacion y orden del selector", () => {
  assert.equal(etiquetaResultadoReconciliacion("pagado"), "El pago estaba aprobado: el pedido pasó a Pagado");
  assert.equal(etiquetaResultadoReconciliacion("en_curso"), "El pago sigue en curso en Wompi");
  assert.equal(
    etiquetaResultadoReconciliacion("libre"),
    "No hay un pago aprobado: el pedido sigue sin pagar",
  );
  assert.deepEqual(destinosParaSelector("pagado").map((a) => a.destino), ["en_preparacion", "incidencia"]);
  assert.deepEqual(destinosParaSelector("incidencia").map((a) => a.destino), ["en_preparacion", "cancelado"]);
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

test("destinoComunDeLote y resumenDeLote", () => {
  const p = (estado: Pedido["estado"]) => pedido({ estado });
  assert.equal(destinoComunDeLote([p("pagado"), p("pagado"), p("pagado")]), "en_preparacion");
  assert.equal(destinoComunDeLote([p("despachado")]), "en_reparto");
  assert.equal(destinoComunDeLote([p("en_reparto")]), "entregado");
  assert.equal(destinoComunDeLote([p("pagado"), p("despachado")]), null);
  assert.equal(destinoComunDeLote([p("en_preparacion")]), null);
  assert.equal(destinoComunDeLote([]), null);
  assert.equal(resumenDeLote({ avanzados: [1], fallidos: [] }), "1 avanzado, 0 con problema");
  assert.equal(resumenDeLote({ avanzados: Array(18), fallidos: [1, 2] }), "18 avanzados, 2 con problema");
});

test("hrefConAlerta conserva los otros filtros", async () => {
  const { hrefConAlerta } = await import("../src/lib/logistica.ts");
  const f = leerFiltros({ estado: "pagado", alerta: "pago_atascado" });
  assert.equal(hrefConAlerta(f, "pagado_sin_avanzar"), "/logistica?estado=pagado&alerta=pagado_sin_avanzar");
  assert.equal(hrefConAlerta(leerFiltros({}), ""), "/logistica");
});

// ---------------------------------------------------------- Tablero kanban
import {
  accionDeTarjeta,
  agruparPorEtapa,
  articulosDePedido,
  CARRIL_APARTE,
  COLUMNAS_FLUJO,
  hrefConVista,
  hrefEtapaEnTabla,
  hrefConAlerta,
  PRIORIDAD_ESTADO,
} from "../src/lib/logistica.ts";

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
  // Los chips de alerta, desde la tabla, siguen en la tabla.
  assert.equal(hrefConAlerta(f, ""), "/logistica?vista=tabla");
  assert.equal(hrefEtapaEnTabla(leerFiltros({}), "entregado"), "/logistica?estado=entregado&vista=tabla");
});

test("las columnas siguen el flujo y lo que sale de el va aparte", () => {
  assert.deepEqual([...COLUMNAS_FLUJO, ...CARRIL_APARTE].sort(), Object.keys(PRIORIDAD_ESTADO).sort());
  assert.deepEqual(CARRIL_APARTE, ["incidencia", "cancelado"]);
});

test("agruparPorEtapa: conteo real, alertas y lo mas viejo primero; cerrados recortados", () => {
  const dia = (d: number) => `2026-10-${String(d).padStart(2, "0")}T15:00:00Z`;
  const pedidos = [
    pedido({ pedido_id: "p-viejo", creado_en: dia(1) }),
    pedido({ pedido_id: "p-nuevo", creado_en: dia(5) }),
    pedido({ pedido_id: "p-alerta", creado_en: dia(9), alertas: ["pagado_sin_avanzar"] }),
    ...Array.from({ length: 7 }, (_, i) =>
      pedido({ pedido_id: `e-${i}`, estado: "entregado", creado_en: dia(1), envio: { entregado_en: dia(10 + i) } as Pedido["envio"] }),
    ),
  ];
  const [pagado, entregado] = agruparPorEtapa(pedidos, ["pagado", "entregado"], 5);
  assert.deepEqual(pagado!.pedidos.map((p) => p.pedido_id), ["p-alerta", "p-viejo", "p-nuevo"]);
  assert.equal(pagado!.ocultos, 0);
  assert.equal(entregado!.total, 7);
  assert.equal(entregado!.pedidos.length, 5);
  assert.equal(entregado!.ocultos, 2);
  // Lo entregado mas reciente primero (por `entregado_en`).
  assert.equal(entregado!.pedidos[0]!.pedido_id, "e-6");
  assert.deepEqual(agruparPorEtapa([], ["en_reparto"])[0], { estado: "en_reparto", total: 0, pedidos: [], ocultos: 0 });
});

test("accionDeTarjeta: solo el avance legal de la matriz, sin saltos", () => {
  for (const estado of [...COLUMNAS_FLUJO, ...CARRIL_APARTE]) {
    const a = accionDeTarjeta(estado);
    if (!a) continue;
    // Siempre una transicion que la matriz permite desde ese estado.
    assert.ok(accionesDisponibles(estado).some((x) => x.destino === a.accion.destino));
    assert.notEqual(a.accion.destino, "incidencia");
    assert.notEqual(a.accion.destino, "cancelado");
  }
  assert.deepEqual(accionDeTarjeta("pagado"), {
    accion: accionesDisponibles("pagado")[0],
    directa: true,
  });
  // Despachar pide repartidor: va al detalle.
  assert.equal(accionDeTarjeta("en_preparacion")!.directa, false);
  assert.equal(accionDeTarjeta("en_reparto")!.accion.destino, "entregado");
  for (const quieto of ["pendiente_pago", "entregado", "cancelado", "incidencia"] as const) {
    assert.equal(accionDeTarjeta(quieto), null);
  }
});

test("articulosDePedido suma cantidades", () => {
  assert.equal(articulosDePedido({ lineas: [] }), 0);
  assert.equal(
    articulosDePedido({ lineas: [{ cantidad: 2 }, { cantidad: 3 }] as Pedido["lineas"] }),
    5,
  );
});
