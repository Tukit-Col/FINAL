// Reglas de la pantalla de progreso: qué paso ya hizo el backend y cuándo la
// cortesía visual avanza el paso que se ve.
// Correr: `node --test test/progreso-espera.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DURACION_PASO_MS,
  PASOS,
  pasosHechosPorBackend,
  siguienteMovimiento,
} from "../src/lib/progreso-espera.ts";

const ok = (nombre: string) => ({ nombre, estado: "ok" });

test("el backend cuenta pasos completos desde el primero", () => {
  assert.equal(pasosHechosPorBackend([], false), 0);
  assert.equal(pasosHechosPorBackend([ok("percepcion")], false), 1);
  // Buscar necesita normalizacion Y resolucion.
  assert.equal(pasosHechosPorBackend([ok("percepcion"), ok("normalizacion")], false), 1);
  assert.equal(pasosHechosPorBackend([ok("percepcion"), ok("normalizacion"), ok("resolucion")], false), 2);
  // Un hueco corta la cuenta aunque haya etapas posteriores.
  assert.equal(pasosHechosPorBackend([ok("resolucion"), ok("optimizacion")], false), 0);
});

test("la revisión final solo la cierra el estado terminal", () => {
  const todas = ["percepcion", "normalizacion", "resolucion", "optimizacion"].map(ok);
  assert.equal(pasosHechosPorBackend(todas, false), 3);
  assert.equal(pasosHechosPorBackend(todas, true), PASOS.length);
});

test("cada paso se ve al menos la duración completa", () => {
  assert.deepEqual(siguienteMovimiento(0, 4, 400), { visibles: 0, enMs: DURACION_PASO_MS - 400 });
  assert.deepEqual(siguienteMovimiento(0, 4, DURACION_PASO_MS), { visibles: 1, enMs: DURACION_PASO_MS });
});

test("nunca se adelanta al backend", () => {
  assert.deepEqual(siguienteMovimiento(1, 1, 9999), { visibles: 1, enMs: null });
  assert.deepEqual(siguienteMovimiento(1, 2, 9999), { visibles: 2, enMs: null });
});

test("si el backend ya terminó, el recorrido entero cabe en ~6 s", () => {
  let visibles = 0;
  let total = 0;
  let desde = 0;
  for (let i = 0; i < 20 && visibles < PASOS.length; i++) {
    const m = siguienteMovimiento(visibles, PASOS.length, desde);
    if (m.enMs === null) break;
    total += m.enMs;
    desde = DURACION_PASO_MS; // el reloj ya cumplió
    const hecho = siguienteMovimiento(visibles, PASOS.length, desde);
    visibles = hecho.visibles;
    desde = 0;
  }
  assert.equal(visibles, PASOS.length);
  assert.ok(total <= 6000);
});
