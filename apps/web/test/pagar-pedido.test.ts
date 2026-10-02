// Pruebas de la regla que decide si el acudiente puede pagar un pedido desde
// "Mis pedidos". Runner nativo de Node (type-stripping), sin dependencias:
// `node --test apps/web/test/pagar-pedido.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { decidirPagoPedido } from "../src/lib/pagar-pedido.ts";

const pendiente = { pedido_id: "p-1", estado: "pendiente_pago" } as const;
const pagado = { pedido_id: "p-2", estado: "pagado" } as const;

test("un pedido propio y pendiente se puede pagar", () => {
  assert.deepEqual(decidirPagoPedido([pendiente, pagado], "p-1"), { ok: true });
});

test("un pedido que no es del acudiente responde 404, igual que uno inexistente", () => {
  assert.deepEqual(decidirPagoPedido([pagado], "p-ajeno"), {
    ok: false,
    estado: 404,
    error: "pedido_no_existe",
    mensaje: "No encontramos ese pedido en tu cuenta.",
  });
});

test("un pedido que ya no esta pendiente responde 409", () => {
  assert.deepEqual(decidirPagoPedido([pagado], "p-2"), {
    ok: false,
    estado: 409,
    error: "pedido_no_pagable",
    mensaje: "Este pedido ya no está pendiente de pago.",
  });
});
