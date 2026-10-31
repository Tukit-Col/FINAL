// Pruebas de la ruta de "Recibimos tu lista": cuantas listas se subieron, cuantas
// quedaron diferidas porque el catalogo no respondia (ADR 0040) y el kit
// instantaneo, si lo hay. Runner nativo de Node (type-stripping), sin
// dependencias: `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { cuantasDiferidas, esDiferida, rutaRecibimos } from "../src/lib/recibimos.ts";

const importada = { version_id: "v-1" } as const;
const diferida = { version_id: null, estado: "pendiente" } as const;

test("con el catalogo arriba la ruta es la de siempre", () => {
  assert.equal(rutaRecibimos([importada, importada]), "/recibimos?pendientes=2");
  assert.equal(rutaRecibimos([importada], "t-1"), "/recibimos?pendientes=1&trabajo=t-1");
});

test("las listas que quedaron pendientes viajan aparte como diferidas", () => {
  assert.equal(rutaRecibimos([importada, diferida]), "/recibimos?pendientes=2&diferidas=1");
  assert.equal(
    rutaRecibimos([diferida, diferida], "t-1"),
    "/recibimos?pendientes=2&diferidas=2&trabajo=t-1",
  );
});

test("una subida sin version cuenta como diferida aunque no traiga estado", () => {
  assert.equal(esDiferida({ version_id: null }), true);
  assert.equal(esDiferida(importada), false);
});

test("el numero de diferidas de la URL se acota a las listas subidas", () => {
  assert.equal(cuantasDiferidas(undefined, 2), 0);
  assert.equal(cuantasDiferidas("abc", 2), 0);
  assert.equal(cuantasDiferidas("0", 2), 0);
  assert.equal(cuantasDiferidas("1", 2), 1);
  assert.equal(cuantasDiferidas("9", 2), 2);
});
