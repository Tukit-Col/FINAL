// El contrato de logistica del back-office: los cuatro metodos de comercio
// reciben el token PRIMERO y obligatorio (comercio valida la sesion y el rol),
// `misPedidos` identifica al acudiente solo por su token, y el detalle trae el
// historial.
// Doble tipado `Pick<OrigenDatos, ...>` — TS verifica que las firmas calcen sin
// stubear todo el origen (el cliente HTTP lo cubre `npm run typecheck`).
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/logistica.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos } from "../src/origen.ts";
import type { Pedido, PedidoConHistorial, SolicitudAvancePedido } from "../src/comercio.ts";

const PEDIDO: PedidoConHistorial = {
  pedido_id: "p1",
  trabajo_id: null,
  estado: "despachado",
  creado_en: "2026-10-03T12:00:00Z",
  total: 9000,
  hijos: 1,
  colegios: ["Colegio San Jose"],
  lineas: [],
  pago: null,
  envio: {
    destinatario: "Ana Perez",
    direccion: "Calle 1 # 2-3",
    ciudad: "Bogota",
    telefono: null,
    departamento: null,
    documento_destinatario: null,
    indicaciones: null,
    transportadora: null,
    guia: null,
    repartidor_nombre: "Luis",
    repartidor_celular: "3001234567",
    entrega_estimada: null,
    entregado_en: null,
  },
  historial: [
    {
      estado_desde: "en_preparacion",
      estado_hacia: "despachado",
      actor_id: "op-1",
      nota: null,
      tipo_incidencia: null,
      creado_en: "2026-10-03T12:00:00Z",
    },
  ],
};

const llamadas: unknown[][] = [];

const origen: Pick<OrigenDatos, "pedidos" | "pedido" | "avanzarPedido" | "misPedidos"> = {
  async pedidos(token: string) {
    llamadas.push(["pedidos", token]);
    return {
      resumen: {
        pedidos_totales: 1,
        por_estado: {
          pendiente_pago: 0,
          pagado: 0,
          en_preparacion: 0,
          despachado: 1,
          en_reparto: 0,
          entregado: 0,
          incidencia: 0,
          cancelado: 0,
        },
        ingresos_confirmados: 9000,
        entregas_pendientes: 1,
      },
      pedidos: [PEDIDO],
    };
  },
  async pedido(token: string, pedidoId: string) {
    llamadas.push(["pedido", token, pedidoId]);
    return PEDIDO;
  },
  async avanzarPedido(token: string, pedidoId: string, cuerpo: SolicitudAvancePedido) {
    llamadas.push(["avanzarPedido", token, pedidoId, cuerpo]);
    return { ...PEDIDO, estado: cuerpo.destino };
  },
  async misPedidos(token: string): Promise<Pedido[]> {
    llamadas.push(["misPedidos", token]);
    return [PEDIDO];
  },
};

test("los metodos de logistica reciben el token primero", async () => {
  llamadas.length = 0;
  await origen.pedidos("tok-op");
  await origen.pedido("tok-op", "p1");
  await origen.avanzarPedido("tok-op", "p1", { destino: "en_reparto" });
  await origen.misPedidos("tok-acud");
  assert.deepEqual(
    llamadas.map((l) => l[1]),
    ["tok-op", "tok-op", "tok-op", "tok-acud"],
  );
});

test("el detalle trae el historial y el celular del repartidor", async () => {
  const detalle = await origen.pedido("tok-op", "p1");
  assert.equal(detalle.historial[0]!.estado_hacia, "despachado");
  assert.equal(detalle.envio!.repartidor_celular, "3001234567");
});

test("avanzarPedido devuelve el detalle actualizado", async () => {
  const detalle = await origen.avanzarPedido("tok-op", "p1", {
    destino: "despachado",
    repartidor_nombre: "Luis",
    repartidor_celular: "3001234567",
    entrega_estimada: "2026-10-05T00:00:00-05:00",
  });
  assert.equal(detalle.estado, "despachado");
});
