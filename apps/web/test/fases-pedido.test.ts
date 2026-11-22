import { test } from "node:test";
import assert from "node:assert/strict";
import type { LineaDeTiempoPedido, PasoLineaDeTiempo, PasoPedido, SituacionPaso } from "@tukit/contrato";
import { ETIQUETA_FASE_SEGUIMIENTO, FASES_SEGUIMIENTO } from "@tukit/contrato/comercio";
import { seguimientoDePedido } from "../src/lib/fases-pedido.ts";

const ORDEN: PasoPedido[] = ["creado", "pagado", "en_preparacion", "despachado", "en_reparto", "entregado"];

function linea(actual: PasoPedido | null, extra: Partial<LineaDeTiempoPedido> = {}, hastaHecho?: PasoPedido): LineaDeTiempoPedido {
  const pos = ORDEN.indexOf(actual ?? hastaHecho!);
  const pasos: PasoLineaDeTiempo[] = ORDEN.map((paso, i) => {
    const estado: SituacionPaso = i < pos ? "hecho" : i === pos ? (actual ? "actual" : "hecho") : "futuro";
    return { paso, estado, fecha: estado === "futuro" ? null : `2026-11-0${i + 1}T10:00:00-05:00` };
  });
  return { pasos, especial: null, entrega_estimada: null, pago_pendiente: null, ...extra };
}

test("las fases son las de seguimiento del contrato, sin 'creado', con su nombre para el acudiente", () => {
  const v = seguimientoDePedido(linea("en_preparacion"));
  assert.deepEqual(v.fases.map((f) => f.paso), [...FASES_SEGUIMIENTO]);
  assert.ok(!v.fases.some((f) => f.paso === "creado"));
  for (const f of v.fases) assert.equal(f.etiqueta, ETIQUETA_FASE_SEGUIMIENTO[f.paso]);
});

test("preparando: pagado hecho, preparando actual, el resto futuro", () => {
  const v = seguimientoDePedido(linea("en_preparacion"));
  assert.deepEqual(v.fases.map((f) => f.situacion), ["hecho", "actual", "futuro", "futuro", "futuro"]);
  assert.equal(v.hechas, 1);
  assert.equal(v.actual?.paso, "en_preparacion");
  assert.equal(v.fases[4]!.fecha, null);
});

test("entregado: todas hechas, sin fase actual, sin fecha estimada", () => {
  const v = seguimientoDePedido(linea("entregado", { entrega_estimada: "2026-11-20T00:00:00-05:00" }));
  assert.ok(v.fases.every((f) => f.situacion === "hecho"));
  assert.equal(v.actual, null);
  assert.equal(v.entregado, true);
  assert.equal(v.entregaEstimada, null);
});

test("pendiente de pago: ninguna fase empezo", () => {
  const v = seguimientoDePedido(
    linea("creado", { pago_pendiente: { vence_en: "2026-11-13T10:00:00-05:00", vencido: false } }),
  );
  assert.equal(v.esperaPago, true);
  assert.ok(v.fases.every((f) => f.situacion === "futuro"));
});

test("en reparto con fecha estimada y repartidor en despachado", () => {
  const l = linea("en_reparto", { entrega_estimada: "2026-11-15T00:00:00-05:00" });
  l.pasos.find((p) => p.paso === "despachado")!.repartidor_nombre = "Carlos";
  const v = seguimientoDePedido(l);
  assert.equal(v.entregaEstimada, "2026-11-15T00:00:00-05:00");
  assert.equal(v.fases[2]!.repartidor, "Carlos");
  assert.equal(v.actual?.paso, "en_reparto");
});

test("incidencia: mensaje amable con el motivo, sin nota interna", () => {
  const v = seguimientoDePedido(
    linea("en_reparto", { especial: { tipo: "incidencia", tipo_incidencia: "no_habia_nadie", fecha: null } }),
  );
  assert.equal(v.desvio?.tipo, "incidencia");
  assert.match(v.desvio!.mensaje, /no había nadie/);
  assert.equal(v.resumen, v.desvio!.mensaje);
});

test("un tipo de incidencia desconocido se nombra en generico", () => {
  const v = seguimientoDePedido(
    linea("despachado", { especial: { tipo: "incidencia", tipo_incidencia: "algo_nuevo", fecha: null } }),
  );
  assert.match(v.desvio!.mensaje, /otro inconveniente/);
});

test("cancelado: lo alcanzado queda hecho, no hay fase actual ni estimada", () => {
  const v = seguimientoDePedido(
    linea(null, { especial: { tipo: "cancelado", fecha: "2026-11-03T09:00:00-05:00" }, entrega_estimada: "2026-11-20T00:00:00-05:00" }, "pagado"),
  );
  assert.equal(v.desvio?.tipo, "cancelado");
  assert.equal(v.actual, null);
  assert.deepEqual(v.fases.map((f) => f.situacion), ["hecho", "futuro", "futuro", "futuro", "futuro"]);
  assert.equal(v.entregaEstimada, null);
});
