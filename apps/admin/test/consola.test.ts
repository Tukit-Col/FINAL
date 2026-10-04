// Prueba de los textos de la consola del admin (`lib/consola`).
//
// Correr:  node --test test/consola.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { ClaseLinea } from "@tukit/contrato";
import { resumenPendientes, tituloClaseAdmin } from "../src/lib/consola.ts";

// Un `TITULO_CLASE` de mentira: la prueba no carga el contrato en tiempo de
// ejecución, y así se ve qué clases conservan el título de la web.
const WEB = new Proxy({} as Record<ClaseLinea, string>, {
  get: (_objetivo, clase) => `web:${String(clase)}`,
});

test("los grupos dicen qué hacer con ellos", () => {
  assert.equal(tituloClaseAdmin("pendiente_revision", WEB), "Dudosas: confirma el producto");
  assert.equal(tituloClaseAdmin("hueco", WEB), "No lo tenemos");
  assert.equal(tituloClaseAdmin("sin_match", WEB), "No entendimos qué pide");
  assert.equal(tituloClaseAdmin("licencia_digital", WEB), "Se paga por fuera");
  assert.equal(tituloClaseAdmin("comprable", WEB), "Resueltas");
});

test("las demás clases conservan el título del contrato", () => {
  assert.equal(tituloClaseAdmin("no_comprar", WEB), "web:no_comprar");
  assert.equal(tituloClaseAdmin("informativa", WEB), "web:informativa");
});

test("la cabecera cuenta dudosas sin decidir y huecos", () => {
  assert.equal(resumenPendientes(3, 2), "3 dudosas sin decidir · 2 huecos");
  assert.equal(resumenPendientes(1, 1), "1 dudosa sin decidir · 1 hueco");
  assert.equal(resumenPendientes(0, 0), "0 dudosas sin decidir · 0 huecos");
});
