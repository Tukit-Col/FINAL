import { test } from "node:test";
import assert from "node:assert/strict";
import { AYUDA, sugerenciasDe } from "../src/components/asistente/sugerencias.ts";

test("sin conversacion hay de 3 a 4 sugerencias y la ayuda esta", () => {
  const s = sugerenciasDe("ninguna", null);
  assert.ok(s.length >= 3 && s.length <= 4);
  assert.ok(s.includes(AYUDA));
});

test("tras un mas barato se ofrece lo contrario en la misma categoria", () => {
  const s = sugerenciasDe("propuesta", { accion: "mas_barato", categoria: "colores" });
  assert.equal(s[0], "Mejor calidad en colores");
});

test("no repite lo recien tocado mientras haya otras, y no queda vacia", () => {
  const s = sugerenciasDe("texto", null, ["Más barato en cuadernos"]);
  assert.ok(!s.includes("Más barato en cuadernos"));
  assert.equal(new Set(s).size, s.length);
  assert.ok(s.length >= 3);
});

test("ninguna sugerencia es un pedido en lote", () => {
  for (const u of ["ninguna", "ayuda", "texto", "propuesta"] as const)
    for (const s of sugerenciasDe(u, { accion: "variar", categoria: "kit" }))
      assert.doesNotMatch(s, /todos los|a una marca/i);
});
