// Pruebas de las reglas de "Mis pedidos": si el acudiente puede pagar o
// cancelar un pedido, y cuando un pedido vencio. Runner nativo de Node
// (type-stripping), sin dependencias: `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { compraDeSolicitud, decidirAccionPedido, pedidoVencido, tonoEstadoPedido } from "../src/lib/pagar-pedido.ts";

const AHORA = Date.parse("2026-10-03T12:00:00Z");
const hace = (horas: number) => new Date(AHORA - horas * 3600_000).toISOString();

const pendiente = { pedido_id: "p-1", estado: "pendiente_pago", creado_en: hace(1) } as const;
const pagado = { pedido_id: "p-2", estado: "pagado", creado_en: hace(1) } as const;
const vencido = { pedido_id: "p-3", estado: "pendiente_pago", creado_en: hace(25) } as const;

test("un pedido de mas de 24 horas esta vencido; uno de 23, no", () => {
  assert.equal(pedidoVencido(hace(25), AHORA), true);
  assert.equal(pedidoVencido(hace(23), AHORA), false);
});

test("un pedido propio, pendiente y vigente se puede pagar", () => {
  assert.deepEqual(decidirAccionPedido([pendiente, pagado], "p-1", "pagar", AHORA), { ok: true });
});

test("un pedido que no es del acudiente responde 404, igual que uno inexistente", () => {
  assert.deepEqual(decidirAccionPedido([pagado], "p-ajeno", "pagar", AHORA), {
    ok: false,
    estado: 404,
    error: "pedido_no_existe",
    mensaje: "No encontramos ese pedido en tu cuenta.",
  });
});

test("un pedido que ya no esta pendiente no se paga ni se cancela", () => {
  for (const accion of ["pagar", "cancelar"] as const) {
    assert.deepEqual(decidirAccionPedido([pagado], "p-2", accion, AHORA), {
      ok: false,
      estado: 409,
      error: "pedido_no_pendiente",
      mensaje: "Este pedido ya no está pendiente de pago.",
    });
  }
});

test("un pedido vencido no se paga", () => {
  assert.deepEqual(decidirAccionPedido([vencido], "p-3", "pagar", AHORA), {
    ok: false,
    estado: 409,
    error: "pedido_vencido",
    mensaje: "Este pedido tiene más de 24 horas. Vuelve a armar tu kit para ver el precio de hoy.",
  });
});

test("un pedido vencido si se puede cancelar, para liberar lo reservado", () => {
  assert.deepEqual(decidirAccionPedido([vencido], "p-3", "cancelar", AHORA), { ok: true });
});

test("el tono del estado: verde pagado y entrega, amarillo pendiente, rojo cancelado", () => {
  assert.equal(tonoEstadoPedido("pagado"), "exito");
  assert.equal(tonoEstadoPedido("en_preparacion"), "exito");
  assert.equal(tonoEstadoPedido("entregado"), "exito");
  assert.equal(tonoEstadoPedido("pendiente_pago"), "aviso");
  assert.equal(tonoEstadoPedido("cancelado"), "peligro");
  assert.equal(tonoEstadoPedido("incidencia"), "peligro");
});

const kit = "t-1";
const pedidoDe = (
  pedido_id: string,
  estado: "pendiente_pago" | "pagado" | "cancelado" | "entregado",
  horas: number,
  trabajo_id: string | null = kit,
) => ({ pedido_id, estado, trabajo_id, creado_en: hace(horas) });

test("un kit con pedido pagado queda comprado, con el pedido mas reciente", () => {
  const pedidos = [pedidoDe("viejo", "pagado", 5), pedidoDe("nuevo", "entregado", 2), pedidoDe("x", "cancelado", 1)];
  assert.deepEqual(compraDeSolicitud(kit, pedidos, AHORA), { estado: "comprado", pedidoId: "nuevo" });
});

test("pagado gana sobre un pendiente del mismo kit", () => {
  const pedidos = [pedidoDe("pend", "pendiente_pago", 1), pedidoDe("pag", "pagado", 3)];
  assert.deepEqual(compraDeSolicitud(kit, pedidos, AHORA), { estado: "comprado", pedidoId: "pag" });
});

test("un kit con pedido pendiente y vigente queda por pagar", () => {
  assert.deepEqual(compraDeSolicitud(kit, [pedidoDe("pend", "pendiente_pago", 1)], AHORA), {
    estado: "por_pagar",
    pedidoId: "pend",
  });
});

test("un pendiente vencido, uno cancelado o uno de otro kit no cambian la solicitud", () => {
  const pedidos = [
    pedidoDe("venc", "pendiente_pago", 30),
    pedidoDe("canc", "cancelado", 1),
    pedidoDe("otro", "pagado", 1, "t-2"),
  ];
  assert.equal(compraDeSolicitud(kit, pedidos, AHORA), null);
});
