// Prueba del cuerpo de "confirmo el elegido" (`lib/lote`): se manda el sku del
// producto elegido, no `{}` (con `{}` el backend no sabía qué validar en una
// línea sin candidato y respondía 500).
//
// Correr:  node --test test/lote.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { LineaKit } from "@tukit/contrato";
import { cuerpoValidarElegido } from "../src/lib/lote.ts";

function linea(sku: string | null): Pick<LineaKit, "producto_elegido"> {
  return {
    producto_elegido: sku === null ? null : ({ sku } as LineaKit["producto_elegido"]),
  };
}

test("manda el sku del elegido", () => {
  assert.deepEqual(cuerpoValidarElegido(linea("CUA-100")), { sku: "CUA-100" });
});

test("una línea sin producto no tiene cuerpo", () => {
  assert.equal(cuerpoValidarElegido(linea(null)), null);
  assert.equal(cuerpoValidarElegido({ producto_elegido: undefined }), null);
});
