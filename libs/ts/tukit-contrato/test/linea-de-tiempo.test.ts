// La linea de tiempo del acudiente: Comercio la arma y el contrato solo le pone
// nombre a cada paso. `miPedido` la trae; el tipo se verifica con `Pick` sin
// stubear todo el origen.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/linea-de-tiempo.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos } from "../src/origen.ts";
import type { PasoPedido, PedidoDelAcudiente } from "../src/comercio.ts";
import { ETIQUETA_PASO_PEDIDO } from "../src/comercio.ts";

const PASOS: PasoPedido[] = ["creado", "pagado", "en_preparacion", "despachado", "en_reparto", "entregado"];

test("cada paso de la linea de tiempo tiene su nombre, en el orden de Comercio", () => {
  assert.deepEqual(Object.keys(ETIQUETA_PASO_PEDIDO), PASOS);
  assert.equal(ETIQUETA_PASO_PEDIDO.creado, "Pedido creado");
  assert.equal(ETIQUETA_PASO_PEDIDO.pagado, "Pago confirmado");
  assert.equal(ETIQUETA_PASO_PEDIDO.en_preparacion, "En preparación");
});

test("miPedido devuelve el pedido con su linea de tiempo", async () => {
  const pedido: PedidoDelAcudiente = {
    pedido_id: "p1",
    usuario_id: "u1",
    trabajo_id: null,
    estado: "incidencia",
    creado_en: "2026-10-03T12:00:00+00:00",
    total: 9000,
    hijos: 1,
    colegios: [],
    lineas: [],
    pago: null,
    envio: null,
    linea_de_tiempo: {
      pasos: PASOS.map((paso, i) => ({
        paso,
        estado: i < 3 ? "hecho" : i === 3 ? "actual" : "futuro",
        fecha: i <= 3 ? "2026-10-03T12:00:00+00:00" : null,
        ...(paso === "despachado" ? { repartidor_nombre: "Luis" } : {}),
      })),
      especial: { tipo: "incidencia", tipo_incidencia: "no_habia_nadie", fecha: null },
      entrega_estimada: null,
      pago_pendiente: null,
    },
  };
  const origen: Pick<OrigenDatos, "miPedido"> = {
    async miPedido(token, pedidoId) {
      assert.equal(token, "t");
      assert.equal(pedidoId, "p1");
      return pedido;
    },
  };
  const leido = await origen.miPedido("t", "p1");
  assert.equal(leido.linea_de_tiempo.pasos.find((p) => p.estado === "actual")?.paso, "despachado");
});
