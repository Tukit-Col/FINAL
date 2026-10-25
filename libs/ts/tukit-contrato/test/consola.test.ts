// La consola manda el Bearer de la cookie en toda llamada `/v1/admin/*`, y en
// ninguna otra: el gateway cierra la consola sin sesion del equipo (1.12).
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/consola.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { autorizacionDeConsola, esRutaDeConsola } from "../src/consola.ts";

test("las rutas de la consola se reconocen por su prefijo", () => {
  assert.equal(esRutaDeConsola("/v1/admin"), true);
  assert.equal(esRutaDeConsola("/v1/admin/cola"), true);
  assert.equal(esRutaDeConsola("/v1/admin/listas?estado=pendiente"), true);
  assert.equal(esRutaDeConsola("/v1/admin/trabajos/abc/revision"), true);
});

test("las escrituras de consola fuera de /v1/admin tambien llevan la sesion", () => {
  // Editar, retirar o reclasificar un producto y editar un colegio: el gateway
  // las cierra sin sesion del equipo aunque no cuelguen de /v1/admin.
  assert.equal(esRutaDeConsola("/v1/catalogo/productos/TK-001"), true);
  assert.equal(esRutaDeConsola("/v1/catalogo/productos/TK-001/reclasificar"), true);
  assert.equal(esRutaDeConsola("/v1/colegios/abc"), true);
  // El listado y lo que cuelga de un colegio no son esas escrituras.
  assert.equal(esRutaDeConsola("/v1/colegios"), false);
  assert.equal(esRutaDeConsola("/v1/colegios/abc/grados"), false);
});

test("lo que no es consola no se confunde por parecido", () => {
  assert.equal(esRutaDeConsola("/v1/administrar"), false);
  assert.equal(esRutaDeConsola("/v1/catalogo/productos"), false);
  assert.equal(esRutaDeConsola("/v1/trabajos?admin=1"), false);
});

test("la llamada de consola lleva el Bearer de la sesion", () => {
  assert.deepEqual(autorizacionDeConsola("/v1/admin/cola", "tok"), { Authorization: "Bearer tok" });
});

test("sin token, o fuera de la consola, no se agrega nada", () => {
  assert.deepEqual(autorizacionDeConsola("/v1/admin/cola", undefined), {});
  assert.deepEqual(autorizacionDeConsola("/v1/admin/cola", ""), {});
  assert.deepEqual(autorizacionDeConsola("/v1/trabajos", "tok"), {});
});
