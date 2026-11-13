// Ficha del cliente: filtrado por titular, resumen, actividad y privacidad.
// Correr:  node --test test/cliente-detalle.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { AcudienteAdmin, Caso, Pedido } from "@tukit/contrato";
import {
  construirActividad,
  esUuid,
  hijosSeguros,
  pedidosDelCliente,
  resumenDelCliente,
  solicitudesDePedidos,
} from "../src/lib/cliente-detalle.ts";

const ped = (id: string, usuario: string, estado: string, total: number, creado: string, trabajo: string | null = null) =>
  ({ pedido_id: id, usuario_id: usuario, estado, total, creado_en: creado, trabajo_id: trabajo }) as unknown as Pedido;

const pedidos = [
  ped("p1aaaaaaaa", "u1", "entregado", 100, "2026-10-01T00:00:00Z", "t1"),
  ped("p2bbbbbbbb", "u2", "pagado", 50, "2026-10-02T00:00:00Z"),
  ped("p3cccccccc", "u1", "en_reparto", 200, "2026-10-05T00:00:00Z", "t1"),
  ped("p4dddddddd", "u1", "pendiente_pago", 30, "2026-10-06T00:00:00Z", "t2"),
  ped("p5eeeeeeee", "u1", "cancelado", 70, "2026-10-07T00:00:00Z"),
];

test("esUuid", () => {
  assert.ok(esUuid("78958dfe-8233-4994-a5e2-48b22df2e632"));
  assert.ok(!esUuid("../etc"));
});

test("pedidosDelCliente solo del titular, recientes primero", () => {
  const r = pedidosDelCliente(pedidos, "u1");
  assert.deepEqual(r.map((p) => p.pedido_id[1]), ["5", "4", "3", "1"]);
});

test("resumen: ni pendientes ni cancelados cuentan como facturado", () => {
  const r = resumenDelCliente(pedidosDelCliente(pedidos, "u1"));
  assert.deepEqual(r, { pedidos: 4, facturado: 300, enCurso: 1 });
});

test("solicitudes sin repetir ni nulas", () => {
  assert.deepEqual(solicitudesDePedidos(pedidosDelCliente(pedidos, "u1")).sort(), ["t1", "t2"]);
});

test("actividad ordenada, con enlaces", () => {
  const casos = [{ caso_id: "c1", asunto: "Falta un cuaderno", abierto_en: "2026-10-03T00:00:00Z" }] as unknown as Caso[];
  const a = construirActividad({
    acudiente: { creado_en: "2026-09-01T00:00:00Z" },
    pedidos: pedidosDelCliente(pedidos, "u1").slice(0, 1),
    casos,
    etiquetaEstado: () => "Cancelado",
  });
  assert.deepEqual(a.map((e) => e.tipo), ["pedido", "caso", "registro"]);
  assert.equal(a[1].href, "/tickets/c1");
});

test("privacidad: el apodo y el nombre del menor nunca llegan a la ficha", () => {
  const hijos = [
    { colegio_id: "a", colegio_nombre: "Colegio A", grado: "3", apodo: "Sofi", nombre: "Sofia Perez" },
  ] as unknown as AcudienteAdmin["hijos"];
  const seguros = hijosSeguros(hijos);
  assert.deepEqual(seguros, [{ posicion: 1, grado: "3", colegio: "Colegio A" }]);
  const texto = JSON.stringify(seguros);
  assert.ok(!texto.includes("Sofi") && !texto.includes("Perez"));
});
