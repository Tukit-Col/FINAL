// El saludo del panel: el nombre de la cuenta si es un nombre, y si no algo
// neutro; nunca el correo.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/cuenta.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { saludoDeCuenta } from "../src/lib/cuenta.ts";

test("con nombre saluda por el nombre", () => {
  assert.equal(saludoDeCuenta("Ana María"), "Hola, Ana María");
  assert.equal(saludoDeCuenta("  Ana  "), "Hola, Ana");
});

test("sin nombre, o con el correo en su lugar, saluda neutro", () => {
  assert.equal(saludoDeCuenta(""), "Hola");
  assert.equal(saludoDeCuenta("   "), "Hola");
  assert.equal(saludoDeCuenta("qa-ui-papa-104@ejemplo.com"), "Hola");
});
