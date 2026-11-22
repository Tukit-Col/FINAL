import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ETIQUETA_FASE_SEGUIMIENTO,
  ETIQUETA_PASO_PEDIDO,
  ETIQUETA_TIPO_INCIDENCIA,
  FASES_SEGUIMIENTO,
  PASOS_PEDIDO,
  TIPOS_INCIDENCIA,
} from "../src/comercio.ts";

test("cada paso de la linea de tiempo tiene su nombre, en el orden de Comercio", () => {
  assert.deepEqual(PASOS_PEDIDO, ["creado", "pagado", "en_preparacion", "despachado", "en_reparto", "entregado"]);
  assert.deepEqual(Object.keys(ETIQUETA_PASO_PEDIDO), [...PASOS_PEDIDO]);
  const nombres = Object.values(ETIQUETA_PASO_PEDIDO);
  assert.ok(nombres.every((n) => n.trim().length > 0));
  assert.equal(new Set(nombres).size, nombres.length, "dos pasos con el mismo nombre");
});

test("el acudiente sigue cinco fases: 'creado' es el pedido esperando pago, no una fase", () => {
  assert.deepEqual(FASES_SEGUIMIENTO, ["pagado", "en_preparacion", "despachado", "en_reparto", "entregado"]);
  for (const fase of FASES_SEGUIMIENTO) assert.ok(ETIQUETA_FASE_SEGUIMIENTO[fase].trim().length > 0);
});

test("cada tipo de incidencia tiene su nombre", () => {
  assert.deepEqual(Object.keys(ETIQUETA_TIPO_INCIDENCIA).sort(), [...TIPOS_INCIDENCIA].sort());
  assert.ok(Object.values(ETIQUETA_TIPO_INCIDENCIA).every((n) => n.trim().length > 0));
});
