// El contrato de lectura admin de acudientes por colegio: `acudientesDeColegio`
// devuelve una lista de `AcudienteResumen` (usuario_id + estado + fecha + id de
// trabajo). Doble tipado `Pick<OrigenDatos, "acudientesDeColegio">` — TS verifica
// que la firma calce sin stubear todo el origen.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/acudientes.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { AcudienteResumen, OrigenDatos } from "../src/origen.ts";

const origen: Pick<OrigenDatos, "acudientesDeColegio"> = {
  async acudientesDeColegio(_colegioId: string): Promise<AcudienteResumen[]> {
    return [
      { usuario_id: "u1", estado: "procesando", actualizado_en: "2026-09-01T00:00:00Z", trabajo_id: "t1" },
      { usuario_id: "u2", estado: "espera_revision", actualizado_en: "2026-09-01T01:00:00Z", trabajo_id: "t2" },
    ];
  },
};

test("acudientesDeColegio devuelve resúmenes con estado", async () => {
  const filas = await origen.acudientesDeColegio("colegio-1");
  assert.equal(filas.length, 2);
  assert.equal(filas[0]!.estado, "procesando");
  assert.equal(filas[1]!.usuario_id, "u2");
  // No hay campos de menores: solo el identificador del acudiente y el estado.
  assert.deepEqual(Object.keys(filas[0]!).sort(), [
    "actualizado_en",
    "estado",
    "trabajo_id",
    "usuario_id",
  ]);
});
