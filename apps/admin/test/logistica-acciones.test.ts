// Lo que el operador puede hacer con un pedido: las acciones por estado (espejo
// de la matriz de comercio), el avance en lote, la reconciliacion de un pago y
// como se nombra cada fallo de acceso o de la accion.
//
// Correr:  node --test test/logistica-acciones.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { Pedido } from "@tukit/contrato";
import {
  accionesDisponibles,
  claseDeFallo,
  destinoComunDeLote,
  destinosParaSelector,
  etiquetaResultadoReconciliacion,
  fechaEstimadaIso,
  motivoDeAcceso,
  motivoDeFallo,
  motivoSinAcciones,
  resumenDeLote,
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

test("motivoSinAcciones: pendiente_pago ofrece reconciliar y menciona las 24 h", () => {
  const m = motivoSinAcciones("pendiente_pago");
  assert.equal(m?.accion, "reconciliar");
  assert.match(m?.detalle ?? "", /24 h/);
  assert.equal(motivoSinAcciones("entregado")?.accion, undefined);
  assert.equal(motivoSinAcciones("cancelado")?.accion, undefined);
  assert.equal(motivoSinAcciones("pagado"), null);
});

test("cada resultado de reconciliacion se dice, y el selector ofrece los destinos de la matriz", () => {
  assert.equal(etiquetaResultadoReconciliacion("pagado"), "El pago estaba aprobado: el pedido pasó a Pagado");
  assert.equal(etiquetaResultadoReconciliacion("en_curso"), "El pago sigue en curso en Wompi");
  assert.equal(
    etiquetaResultadoReconciliacion("libre"),
    "No hay un pago aprobado: el pedido sigue sin pagar",
  );
  assert.deepEqual(destinosParaSelector("pagado").map((a) => a.destino), ["en_preparacion", "incidencia"]);
  assert.deepEqual(destinosParaSelector("incidencia").map((a) => a.destino), ["en_preparacion", "cancelado"]);
});

test("un lote avanza solo si todos comparten destino, y su resumen pluraliza", () => {
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

test("motivoDeFallo distingue sesion, rol, limite de tasa y caida", () => {
  assert.equal(motivoDeFallo(401), "sesion_expirada");
  assert.equal(motivoDeFallo(403), "sin_rol");
  assert.equal(motivoDeFallo(503), "servicio_caido");
  // Un 429 es el limite de tasa, no un servicio caido ni una sesion vencida.
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

test("claseDeFallo nombra sesion, rol, conflicto y pasarela; lo demas es otro", () => {
  assert.equal(claseDeFallo(401), "sesion");
  assert.equal(claseDeFallo(403), "rol");
  assert.equal(claseDeFallo(409), "conflicto");
  assert.equal(claseDeFallo(502), "pasarela");
  assert.equal(claseDeFallo(500), "otro");
});
