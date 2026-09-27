// El contrato de lectura del panel del acudiente: `misTrabajos` devuelve una
// lista de `TrabajoResumen` (estado + hijos por referencia/colegio/grado +
// preferencias), identificada por el Bearer del portador. Doble tipado
// `Pick<OrigenDatos, "misTrabajos">` — TS verifica que la firma calce sin
// stubear todo el origen.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/mis-trabajos.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos } from "../src/origen.ts";
import type { TrabajoResumen } from "../src/contrato.ts";

const origen: Pick<OrigenDatos, "misTrabajos"> = {
  async misTrabajos(_token?: string): Promise<TrabajoResumen[]> {
    return [
      {
        trabajo_id: "t1",
        estado: "encolado",
        creado_en: "2026-09-01T00:00:00Z",
        hijos: [{ referencia: "hijo-0", colegio_id: "c1", grado: "Cuarto" }],
        preferencias: { disposicion_sobreprecio: 0.2 },
      },
    ];
  },
};

test("misTrabajos devuelve las solicitudes del acudiente", async () => {
  const filas = await origen.misTrabajos("tok-acud");
  assert.equal(filas.length, 1);
  assert.equal(filas[0]!.estado, "encolado");
  assert.equal(filas[0]!.hijos[0]!.grado, "Cuarto");
  // Sin nombre de menor: la referencia es sintética (`hijo-0`).
  assert.equal(filas[0]!.hijos[0]!.referencia, "hijo-0");
});
