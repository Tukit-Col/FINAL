// El contrato de la subida de listas de un acudiente (`POST /v1/listas/subir`):
// con el catalogo arriba cada hijo trae su `version_id`; con el catalogo caido
// la lista igual queda recibida, sin version todavia y con `estado: "pendiente"`
// (ADR 0040). Doble tipado `Pick<OrigenDatos, "subirListas">` — TS verifica que
// la firma calce sin stubear todo el origen.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/subida.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos } from "../src/origen.ts";
import type { SubidaHecha, SubidaListas } from "../src/contrato.ts";

function origenQueResponde(subidas: SubidaHecha[]): Pick<OrigenDatos, "subirListas"> {
  return {
    async subirListas(): Promise<SubidaListas> {
      return { subidas, contacto_referencia: "c-ficticio-1" };
    },
  };
}

test("con el catalogo arriba cada hijo queda ligado a su version", async () => {
  const origen = origenQueResponde([{ referencia: "hijo-0", version_id: "v-1", grado: "Cuarto" }]);
  const { subidas } = await origen.subirListas([], []);
  assert.equal(subidas[0]?.version_id, "v-1");
  assert.equal(subidas[0]?.estado, undefined);
});

test("con el catalogo caido la lista queda recibida y pendiente, sin version", async () => {
  const origen = origenQueResponde([
    { referencia: "hijo-0", version_id: "v-1", grado: "Cuarto" },
    { referencia: "hijo-1", version_id: null, grado: "Quinto", estado: "pendiente" },
  ]);
  const { subidas } = await origen.subirListas([], []);
  const pendientes = subidas.filter((s) => s.estado === "pendiente");
  assert.equal(pendientes.length, 1);
  assert.equal(pendientes[0]?.referencia, "hijo-1");
  assert.equal(pendientes[0]?.version_id, null);
});
