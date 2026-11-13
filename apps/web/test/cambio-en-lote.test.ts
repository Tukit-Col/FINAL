// Plan determinista de cambio en lote. Correr: `node --test test/cambio-en-lote.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { OpcionDeLinea } from "@tukit/contrato";
import { aplicarPlanEnLote, marcasDisponibles, planDeCambioPorMarca } from "../src/lib/cambio-en-lote.ts";

const op = (sku: string, marca: string | null, precio = 1000, en_kit = false) =>
  ({ sku, marca, precio, en_kit }) as unknown as OpcionDeLinea;
const lineas = [{ item_id: "a" }, { item_id: "b" }, { item_id: "c" }];

test("cambia las que tienen la marca y reporta las otras", () => {
  const o = { a: [op("a1", "Norma")], b: [op("b1", "Norma")], c: [op("c1", "Scribe")] };
  const plan = planDeCambioPorMarca(lineas, o, "norma");
  assert.equal(plan.cambian.length, 2);
  assert.deepEqual(plan.sinEsaMarca, ["c"]);
  assert.deepEqual(marcasDisponibles(o)[0], { marca: "Norma", lineas: 2 });
});

test("la que ya tiene la marca no cambia; descartadas se ignoran; gana el menor precio", () => {
  const o = {
    a: [op("a1", "Norma", 500, true)],
    b: [op("b1", "Norma", 900), op("b2", "Norma", 400)],
    c: [op("c1", "Norma")],
  };
  const plan = planDeCambioPorMarca([lineas[0]!, lineas[1]!, { item_id: "c", descartado: true }], o, "Norma");
  assert.deepEqual(plan.cambian, [{ item_id: "b", sku: "b2" }]);
  assert.deepEqual(plan.sinEsaMarca, []);
});

test("un fallo a mitad del lote no detiene el resto", async () => {
  const plan = { cambian: ["a", "b", "c"].map((i) => ({ item_id: i, sku: i + "1" })), sinEsaMarca: [] };
  let n = 0;
  const r = await aplicarPlanEnLote(plan, async () => {
    if (++n === 2) throw new Error("red");
  });
  assert.deepEqual(r, { hechos: 2, fallidos: ["b"] });
});
