// El panel solo muestra lo accionable.
// Correr:  node --test test/panel-accionable.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { ColaAdmin, ResumenComercio, ResumenOperacion } from "@tukit/contrato";
import { construirWidgets } from "../src/lib/panel-accionable.ts";

const pedidos = (extra: Partial<ResumenComercio> = {}): ResumenComercio =>
  ({
    pedidos_totales: 0,
    por_estado: { incidencia: 0 },
    ingresos_confirmados: 0,
    entregas_pendientes: 0,
    alertas: { pagado_sin_avanzar: 0, pago_atascado: 0, incidencia_abierta: 0 },
    ...extra,
  }) as ResumenComercio;

const casos = (extra: Partial<ResumenOperacion> = {}): ResumenOperacion => ({
  abiertos: 0,
  urgentes: 0,
  vencen_hoy: 0,
  resueltos_semana: 0,
  sin_asignar: 0,
  vencidos: 0,
  ...extra,
});

const cola = (estados: string[] = []): ColaAdmin =>
  ({ entradas: estados.map((estado) => ({ estado, lineas_pendientes: 3 })) }) as unknown as ColaAdmin;

test("todo en cero: ningún widget (la página dice 'Todo al día')", () => {
  const r = construirWidgets({ pedidos: pedidos(), casos: casos(), cola: cola() });
  assert.deepEqual(r, { widgets: [], caidos: [], sinActivar: [] });
});

test("un conteo distinto de cero trae su widget con el enlace exacto", () => {
  const r = construirWidgets({
    pedidos: pedidos({ alertas: { pagado_sin_avanzar: 3, pago_atascado: 0, incidencia_abierta: 0 } }),
    casos: casos(),
    cola: cola(),
  });
  assert.equal(r.widgets.length, 1);
  assert.equal(r.widgets[0]!.cantidad, 3);
  assert.equal(r.widgets[0]!.enlace, "/logistica?alerta=pagado_sin_avanzar");
});

test("una fuente caída se reporta y las demás siguen", () => {
  const r = construirWidgets({
    pedidos: pedidos({ alertas: { pagado_sin_avanzar: 2, pago_atascado: 0, incidencia_abierta: 0 } }),
    casos: null,
    cola: cola(["espera_revision"]),
  });
  assert.deepEqual(r.caidos, ["casos"]);
  assert.deepEqual(r.widgets.map((w) => w.id).sort(), ["listas_en_revision", "pagado_sin_avanzar"]);
});

test("orden: alta antes que media y, a igual urgencia, la mayor cantidad primero", () => {
  const r = construirWidgets({
    pedidos: pedidos({ alertas: { pagado_sin_avanzar: 1, pago_atascado: 5, incidencia_abierta: 0 } }),
    casos: casos({ sin_asignar: 9, vencidos: 2 }),
    cola: cola(["espera_revision", "espera_revision"]),
  });
  assert.deepEqual(
    r.widgets.map((w) => w.id),
    ["pago_atascado", "tickets_vencidos", "pagado_sin_avanzar", "tickets_sin_asignar", "listas_en_revision"],
  );
  assert.ok(r.widgets.every((w) => w.cantidad > 0));
});

test("resúmenes viejos (servicio sin reiniciar) no lanzan: cuentan 0 y se anotan", () => {
  const viejoPedidos = { pedidos_totales: 0, por_estado: { incidencia: 2 } } as unknown as ResumenComercio;
  const viejoCasos = { abiertos: 4, urgentes: 0, vencen_hoy: 0, resueltos_semana: 0 } as ResumenOperacion;
  const r = construirWidgets({ pedidos: viejoPedidos, casos: viejoCasos, cola: cola() });
  assert.deepEqual(r.sinActivar.sort(), ["casos", "pedidos"]);
  // las incidencias salen del conteo de siempre
  assert.deepEqual(r.widgets.map((w) => [w.id, w.cantidad]), [["incidencias", 2]]);
});

test("cola: cuenta trabajos esperando y fallidos; la ayuda pluraliza líneas", () => {
  const r = construirWidgets({ pedidos: pedidos(), casos: casos(), cola: cola(["espera_revision", "fallido", "publicado"]) });
  assert.deepEqual(r.widgets.map((w) => [w.id, w.cantidad]), [["listas_en_revision", 1], ["procesos_fallidos", 1]]);
  assert.match(r.widgets[0]!.ayuda, /3 líneas/);
});
