// El detalle de pedido del admin: la linea de tiempo con quien y cuando, el
// enmascarado de datos personales, los totales por linea y como se nombra a
// cada hijo sin su apodo (Ley 1581).
//
// Correr:  node --test test/pedido-admin.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { PedidoAdmin } from "@tukit/contrato";
import {
  construirLineaDeTiempo,
  enmascararCorreo,
  enmascararTelefono,
  formatearDiaIso,
  lineasConSubtotal,
  rotuloDeHijo,
  totalDescuadrado,
} from "../src/lib/pedido-admin.ts";

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

// --- Ley 1581: el apodo de un menor no llega a las vistas admin ---------------
// Que ninguna fuente de `src/` lea `.apodo` lo vigila la regla de lint de
// `eslint.config.mjs`; aqui, que el rotulo no lo deje pasar aunque llegue.

test("el rotulo de un hijo dice su posicion y grado, nunca el apodo que traiga el objeto", () => {
  const rotulo = rotuloDeHijo({ apodo: "Sofi", grado: "3°" } as { grado: string }, 0);
  assert.equal(rotulo, "Hijo 1 · grado 3°");
  assert.ok(!rotulo.includes("Sofi"));
});
