// Prueba de cómo se reparte la cola (`lib/cola`): las vistas previas de lista
// no se cuentan como trabajos de acudiente en espera.
//
// Correr:  node --test test/cola.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { EntradaCola, EstadoTrabajo } from "@tukit/contrato";
import { separarCola } from "../src/lib/cola.ts";

function entrada(trabajo_id: string, estado: EstadoTrabajo, origen: string): EntradaCola {
  return {
    trabajo_id,
    estado,
    recibido_en: "2026-10-01T00:00:00Z",
    hijos: 1,
    lineas_totales: 3,
    lineas_pendientes: 1,
    colegios: ["c1"],
    grados: ["5"],
    origen,
    version_id: origen === "preview_onboarding" ? "v1" : null,
  };
}

test("las vistas previas van aparte de los trabajos de acudiente", () => {
  const { deAcudiente, vistasPrevias } = separarCola([
    entrada("a", "espera_revision", "acudiente"),
    entrada("p", "espera_revision", "preview_onboarding"),
    entrada("g", "espera_revision", "colegio_grado"),
  ]);
  assert.deepEqual(
    deAcudiente.map((e) => e.trabajo_id),
    ["a", "g"],
  );
  assert.deepEqual(
    vistasPrevias.map((e) => e.trabajo_id),
    ["p"],
  );
});

test("solo cuenta lo que está en espera de revisión", () => {
  const { deAcudiente, vistasPrevias } = separarCola([
    entrada("a", "publicado", "acudiente"),
    entrada("b", "procesando", "acudiente"),
    entrada("p", "publicado", "preview_onboarding"),
  ]);
  assert.equal(deAcudiente.length, 0);
  assert.equal(vistasPrevias.length, 0);
});
