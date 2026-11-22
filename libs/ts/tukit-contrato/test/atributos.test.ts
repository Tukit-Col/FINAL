import { test } from "node:test";
import assert from "node:assert/strict";
import { inferirTipoAtributo, serializarAtributos } from "../src/catalogo.ts";

test("inferir tipos", () => {
  assert.equal(inferirTipoAtributo("80"), 80);
  assert.equal(inferirTipoAtributo("3.5"), 3.5);
  assert.equal(inferirTipoAtributo("true"), true);
  assert.equal(inferirTipoAtributo("cuadriculado"), "cuadriculado");
});

test("serializar descarta vacios", () => {
  const r = serializarAtributos([
    { clave: "hojas", valor: "80" },
    { clave: "rayado", valor: "" },
    { clave: "", valor: "x" },
  ]);
  assert.deepEqual(r, { hojas: 80 });
});
