// Ley 1581: el apodo de un menor no llega a las vistas admin.
// Correr:  node --test test/privacidad-admin.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { rotuloDeHijo } from "../src/lib/pedido-admin.ts";

test("rotuloDeHijo no filtra el apodo aunque el objeto lo traiga", () => {
  const rotulo = rotuloDeHijo({ apodo: "Sofi", grado: "3°" } as { grado: string }, 0);
  assert.equal(rotulo, "Hijo 1 · grado 3°");
  assert.ok(!rotulo.includes("Sofi"));
});

function fuentes(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    if (statSync(ruta).isDirectory()) return fuentes(ruta);
    return /\.(ts|tsx)$/.test(n) ? [ruta] : [];
  });
}

test("ninguna fuente de apps/admin/src lee .apodo", () => {
  const culpables = fuentes(new URL("../src", import.meta.url).pathname).filter((f) =>
    /\.apodo\b/.test(readFileSync(f, "utf8")),
  );
  assert.deepEqual(culpables, []);
});
