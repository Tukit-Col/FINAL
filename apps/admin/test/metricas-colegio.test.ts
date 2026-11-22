import { test } from "node:test";
import assert from "node:assert/strict";
import { demandaPorGrado } from "../src/lib/metricas-colegio.ts";

const COLEGIO = "col-1";

function sugerencia(overrides: Record<string, unknown> = {}) {
  return {
    tarea_id: Math.random().toString(36).slice(2),
    estado: "pendiente",
    colegio_id: COLEGIO,
    grado: "Quinto",
    anio_lectivo: 2026,
    contacto_referencia: "padre-1",
    tiene_documento: true,
    ...overrides,
  };
}

test("agrupa por grado y ordena por demanda descendente", () => {
  const demanda = demandaPorGrado(
    [
      sugerencia({ grado: "Quinto", contacto_referencia: "p1" }),
      sugerencia({ grado: "Quinto", contacto_referencia: "p2" }),
      sugerencia({ grado: "Cuarto", contacto_referencia: "p3" }),
    ] as never,
    COLEGIO,
    new Set(),
  );
  assert.deepEqual(demanda, [
    { grado: "Quinto", solicitudes: 2 },
    { grado: "Cuarto", solicitudes: 1 },
  ]);
});

test("no cuenta las copias de nueva versión (contacto nulo)", () => {
  const demanda = demandaPorGrado(
    [
      sugerencia({ grado: "Quinto", contacto_referencia: "p1" }),
      sugerencia({ grado: "Quinto", contacto_referencia: null }),
      sugerencia({ grado: "Quinto", contacto_referencia: null }),
    ] as never,
    COLEGIO,
    new Set(),
  );
  assert.deepEqual(demanda, [{ grado: "Quinto", solicitudes: 1 }]);
});

test("excluye grados con lista verificada", () => {
  const demanda = demandaPorGrado(
    [
      sugerencia({ grado: "Quinto", contacto_referencia: "p1" }),
      sugerencia({ grado: "Cuarto", contacto_referencia: "p2" }),
    ] as never,
    COLEGIO,
    new Set(["Quinto"]),
  );
  assert.deepEqual(demanda, [{ grado: "Cuarto", solicitudes: 1 }]);
});

test("ignora sugerencias de otro colegio y sin grado", () => {
  const demanda = demandaPorGrado(
    [
      sugerencia({ grado: "Quinto", colegio_id: "otro" }),
      sugerencia({ grado: null }),
      sugerencia({ grado: "Cuarto", contacto_referencia: "p1" }),
    ] as never,
    COLEGIO,
    new Set(),
  );
  assert.deepEqual(demanda, [{ grado: "Cuarto", solicitudes: 1 }]);
});

test("empate: orden estable por nombre de grado", () => {
  const demanda = demandaPorGrado(
    [
      sugerencia({ grado: "Segundo", contacto_referencia: "p1" }),
      sugerencia({ grado: "Primero", contacto_referencia: "p2" }),
    ] as never,
    COLEGIO,
    new Set(),
  );
  assert.deepEqual(demanda, [
    { grado: "Primero", solicitudes: 1 },
    { grado: "Segundo", solicitudes: 1 },
  ]);
});
