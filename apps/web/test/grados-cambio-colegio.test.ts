import { test } from "node:test";
import assert from "node:assert/strict";
import { gradosParaCambio } from "../src/lib/grados-cambio-colegio.ts";

const CANON = ["Transición", "1°", "2°", "3°"];

test("ofrece solo los verificados, en orden canónico", () => {
  const r = gradosParaCambio(["3°", "1°"], CANON, "1°");
  assert.deepEqual(r.opciones, ["1°", "3°"]);
  assert.equal(r.seleccionado, "1°");
  assert.equal(r.gradoPerdido, false);
});

test("si el grado actual no está verificado no se conserva en silencio", () => {
  const r = gradosParaCambio(["1°"], CANON, "2°");
  assert.equal(r.seleccionado, "");
  assert.equal(r.gradoPerdido, true);
});

test("sin verificados: sinVerificados y sin aviso de grado perdido", () => {
  const r = gradosParaCambio([], CANON, "2°");
  assert.deepEqual(r.opciones, []);
  assert.equal(r.sinVerificados, true);
  assert.equal(r.gradoPerdido, false);
});
