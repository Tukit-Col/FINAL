// Las reglas de la contrasena del alta de cuenta: se conocen antes de escribir
// y se marcan al cumplirse. Correr con `node --test test/clave.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { CLAVE_MINIMA, claveValida, reglasDeClave } from "../src/linea.ts";

test("las reglas de la contrasena se conocen antes de escribir y se marcan al cumplirse", () => {
  const vacia = reglasDeClave("");
  assert.equal(vacia.length >= 1, true);
  assert.equal(vacia.every((r) => r.cumple === false), true);
  // La regla del largo dice el minimo.
  assert.ok(vacia.some((r) => r.texto.includes(String(CLAVE_MINIMA))));
  assert.ok(reglasDeClave("larguisima1").every((r) => r.cumple));
  assert.equal(claveValida("corta"), false);
  assert.equal(claveValida("larguisima1"), true);
});
