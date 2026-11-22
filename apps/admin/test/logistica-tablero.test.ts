import { test } from "node:test";
import assert from "node:assert/strict";
import type { Pedido } from "@tukit/contrato";
import {
  accionDeTarjeta,
  accionesDisponibles,
  agruparPorEtapa,
  articulosDePedido,
  CARRIL_APARTE,
  COLUMNAS_FLUJO,
  PRIORIDAD_ESTADO,
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
  assert.equal(entregado!.pedidos[0]!.pedido_id, "e-6");
  assert.deepEqual(agruparPorEtapa([], ["en_reparto"])[0], { estado: "en_reparto", total: 0, pedidos: [], ocultos: 0 });
});

test("agruparPorEtapa: las etapas abiertas tambien se recortan, con alertas primero", () => {
  const pedidos = Array.from({ length: 30 }, (_, i) =>
    pedido({
      pedido_id: `p-${i}`,
      creado_en: `2026-10-${String(1 + (i % 28)).padStart(2, "0")}T15:00:00Z`,
      alertas: i === 29 ? ["pagado_sin_avanzar"] : undefined,
    }),
  );
  const [pagado] = agruparPorEtapa(pedidos, ["pagado"]);
  assert.equal(pagado!.total, 30);
  assert.equal(pagado!.pedidos.length, 8);
  assert.equal(pagado!.ocultos, 22);
  assert.equal(pagado!.pedidos[0]!.pedido_id, "p-29");
});

test("accionDeTarjeta: solo el avance legal de la matriz, sin saltos", () => {
  for (const estado of [...COLUMNAS_FLUJO, ...CARRIL_APARTE]) {
    const a = accionDeTarjeta(estado);
    if (!a) continue;
    assert.ok(accionesDisponibles(estado).some((x) => x.destino === a.accion.destino));
    assert.notEqual(a.accion.destino, "incidencia");
    assert.notEqual(a.accion.destino, "cancelado");
  }
  assert.deepEqual(accionDeTarjeta("pagado"), {
    accion: accionesDisponibles("pagado")[0],
    directa: true,
  });
  assert.equal(accionDeTarjeta("en_preparacion")!.directa, false);
  assert.equal(accionDeTarjeta("en_reparto")!.accion.destino, "entregado");
  for (const quieto of ["pendiente_pago", "entregado", "cancelado", "incidencia"] as const) {
    assert.equal(accionDeTarjeta(quieto), null);
  }
});

test("los articulos de un pedido suman las cantidades de sus lineas", () => {
  assert.equal(articulosDePedido({ lineas: [] }), 0);
  assert.equal(
    articulosDePedido({ lineas: [{ cantidad: 2 }, { cantidad: 3 }] as Pedido["lineas"] }),
    5,
  );
});
