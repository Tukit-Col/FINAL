// Validacion de forma de los cuerpos de las rutas proxy de la Fase 4.
// Correr:  node --test test/api-proxy.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validarAsignacion,
  validarDestinoDePrevia,
  validarLote,
  validarNota,
  validarPrioridad,
} from "../src/lib/cuerpos-admin.ts";

const ids = (n: number) => Array.from({ length: n }, (_, i) => `id-${i}`);

test("lote: acepta de 1 a 50 con destino simple", () => {
  assert.equal(validarLote({ pedido_ids: ids(50), destino: "en_preparacion" }).ok, true);
  assert.equal(validarLote({ pedido_ids: ids(1), destino: "entregado" }).ok, true);
});

test("lote: rechaza 51, vacio, repetidos y destinos con datos", () => {
  const r = validarLote({ pedido_ids: ids(51), destino: "en_preparacion" });
  assert.deepEqual(r.ok, false);
  assert.equal(!r.ok && r.campo, "pedido_ids");
  assert.equal(validarLote({ pedido_ids: [], destino: "en_preparacion" }).ok, false);
  assert.equal(validarLote({ pedido_ids: ["a", "a"], destino: "en_preparacion" }).ok, false);
  for (const destino of ["despachado", "incidencia", "cancelado", undefined]) {
    const v = validarLote({ pedido_ids: ["a"], destino });
    assert.equal(v.ok, false);
    assert.equal(!v.ok && v.campo, "destino");
  }
  assert.equal(validarLote(null).ok, false);
});

test("asignacion, prioridad y nota", () => {
  assert.equal(validarAsignacion({ asignar: "yo" }).ok, true);
  assert.equal(validarAsignacion({ asignar: "otro" }).ok, false);
  assert.equal(validarPrioridad({ prioridad: "alta" }).ok, true);
  assert.equal(validarPrioridad({ prioridad: "critica" }).ok, false);
  assert.deepEqual(validarNota({ texto: "  hola " }), { ok: true, valor: "hola" });
  assert.equal(validarNota({ texto: "   " }).ok, false);
  assert.equal(validarNota({ texto: "x".repeat(2001) }).ok, false);
});

test("vista previa: el destino debe ser un estado", () => {
  assert.equal(validarDestinoDePrevia("despachado").ok, true);
  assert.equal(validarDestinoDePrevia(null).ok, false);
  assert.equal(validarDestinoDePrevia("../x").ok, false);
});
