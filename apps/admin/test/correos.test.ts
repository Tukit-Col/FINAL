// Filtros y textos de la pantalla de correos enviados.
// Correr: `node --test test/correos.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { explicarDetalle, hrefCorreos, leerFiltrosCorreos } from "../src/lib/correos.ts";

test("solo se leen filtros válidos de la URL", () => {
  assert.deepEqual(leerFiltrosCorreos({ estado: "fallida", pedido: " AB12 ", caso: "", plantilla: ["pedido_pagado", "x"] }), {
    estado: "fallida",
    pedido: "AB12",
    plantilla: "pedido_pagado",
  });
  assert.deepEqual(leerFiltrosCorreos({ estado: "inventado" }), {});
});

test("un enlace cambia un filtro y conserva los demás; vacío lo quita", () => {
  const filtros = { estado: "fallida" as const, pedido: "AB12" };
  assert.equal(hrefCorreos(filtros, { estado: "omitida" }), "/correos?estado=omitida&pedido=AB12");
  assert.equal(hrefCorreos(filtros, { estado: "", pedido: undefined }), "/correos");
});

test("el detalle del envío se dice en palabras", () => {
  assert.match(explicarDetalle("destino_no_enviable"), /no se intentó/);
  assert.match(explicarDetalle("smtp_error: OSError"), /OSError/);
  assert.equal(explicarDetalle(null), "Sin detalle");
});
