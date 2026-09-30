// Prueba de la lógica pura de la demanda por grado de la sección "Métricas".
// `apps/admin` no tiene runner de componentes; se prueba el helper extraído con
// `node --test` (Node 24 hace type-stripping nativo), igual que
// `atributos-editor.test.ts`.
//
// El foco es la invariante del conteo: solo `sugerencia_padre` con contacto NO
// nulo cuenta (las copias de "Editar (nueva versión)" anulan el contacto y por
// tanto no deben sumar), agrupado por grado, excluyendo grados ya verificados.
//
// Correr:  node --test test/metricas-colegio.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { demandaPorGrado } from "../src/lib/metricas-colegio.ts";

const COLEGIO = "col-1";

// Fábrica mínima: solo los campos que el helper mira.
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
      sugerencia({ grado: "Quinto", contacto_referencia: null }), // copia de edición
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
    new Set(["Quinto"]), // ya tiene lista: no es demanda pendiente
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
