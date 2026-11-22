import { test } from "node:test";
import assert from "node:assert/strict";
import { SIN_FILTROS, SIN_PERSONAJE, filtraProductos, pasaProducto } from "../src/lib/filtros-catalogo.ts";

const lapiz = { nivel: "economico", personaje: null, ofertas: [{ tienda: "Exito" }] };
const cuaderno = { nivel: "premium", personaje: "Frozen", ofertas: [{ tienda: "Panamericana" }, { tienda: "Exito" }] };

test("sin filtros pasa todo y no filtra productos", () => {
  assert.equal(filtraProductos(SIN_FILTROS), false);
  assert.equal(pasaProducto(lapiz, SIN_FILTROS), true);
  assert.equal(pasaProducto(cuaderno, SIN_FILTROS), true);
});

test("el nivel y la tienda filtran por coincidencia exacta", () => {
  assert.equal(pasaProducto(lapiz, { ...SIN_FILTROS, nivel: "premium" }), false);
  assert.equal(pasaProducto(cuaderno, { ...SIN_FILTROS, nivel: "premium" }), true);
  assert.equal(pasaProducto(lapiz, { ...SIN_FILTROS, tienda: "Panamericana" }), false);
  assert.equal(pasaProducto(cuaderno, { ...SIN_FILTROS, tienda: "Panamericana" }), true);
});

test("el filtro de personaje distingue un personaje concreto de sin personaje", () => {
  assert.equal(pasaProducto(cuaderno, { ...SIN_FILTROS, personaje: "Frozen" }), true);
  assert.equal(pasaProducto(lapiz, { ...SIN_FILTROS, personaje: "Frozen" }), false);
  assert.equal(pasaProducto(lapiz, { ...SIN_FILTROS, personaje: SIN_PERSONAJE }), true);
  assert.equal(pasaProducto(cuaderno, { ...SIN_FILTROS, personaje: SIN_PERSONAJE }), false);
  assert.equal(filtraProductos({ ...SIN_FILTROS, personaje: "Frozen" }), true);
});
