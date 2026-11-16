// Categoría derivada de cada línea, agrupación y anclas.
// Correr: `node --test test/categorias-kit.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  agruparPorCategoria,
  categoriaDeLinea,
  idAnclaCategoria,
  idAnclaLinea,
} from "../src/lib/kit-vista.ts";

const l = (descripcion: string, concepto: string | null = null) => ({ descripcion, concepto });

test("categoría por descripción", () => {
  assert.equal(categoriaDeLinea(l("Cuaderno cosido 100 hojas")), "cuadernos");
  assert.equal(categoriaDeLinea(l("Lápiz HB")), "escritura");
  assert.equal(categoriaDeLinea(l("Esfero azul")), "escritura");
  assert.equal(categoriaDeLinea(l("Colores x12")), "arte");
  assert.equal(categoriaDeLinea(l("Témpera")), "arte");
  assert.equal(categoriaDeLinea(l("Regla 30 cm")), "geometria");
  assert.equal(categoriaDeLinea(l("Pegante en barra")), "papeleria");
  assert.equal(categoriaDeLinea(l("Algo raro", null)), "otros");
  assert.equal(categoriaDeLinea(l("Algo raro", "C999")), "otros");
});

test("agrupa en orden fijo, sin vacíos y con otros al final", () => {
  const g = agruparPorCategoria([l("Algo raro"), l("Témpera"), l("Cuaderno A"), l("Cuaderno B")]);
  assert.deepEqual(g.map((x) => x.categoria), ["cuadernos", "arte", "otros"]);
  assert.deepEqual(g[0]!.lineas.map((x) => x.descripcion), ["Cuaderno A", "Cuaderno B"]);
});

test("anclas deterministas, válidas y sin colisión", () => {
  assert.equal(idAnclaCategoria("escritura"), "cat-escritura");
  const a = idAnclaLinea("a b/c");
  assert.equal(a, idAnclaLinea("a b/c"));
  assert.match(a, /^[A-Za-z0-9_.-]+$/);
  assert.notEqual(idAnclaLinea("a b"), idAnclaLinea("a/b"));
  assert.notEqual(idAnclaLinea("a.20.b"), idAnclaLinea("a b"));
});
