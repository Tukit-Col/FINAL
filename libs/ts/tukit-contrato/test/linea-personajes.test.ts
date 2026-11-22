import { test } from "node:test";
import assert from "node:assert/strict";
import { personajesDelKit, personajesPorHijo, productosDelPersonaje } from "../src/linea.ts";
import type { LineaKit, ProductoKit } from "../src/contrato.ts";

function linea(extra: Partial<LineaKit>): LineaKit {
  return {
    item_id: "i-1",
    descripcion: "Cuaderno",
    tipo: "util",
    estado_resolucion: "RESUELTO_AUTO",
    informativa: false,
    subtotal_linea: 9000,
    ...extra,
  } as LineaKit;
}

function producto(extra: Partial<ProductoKit>): ProductoKit {
  return {
    sku: "TK-1",
    nombre: "Cuaderno",
    marca: "Norma",
    nivel: "confiable",
    personaje: null,
    imagen_url: null,
    confianza: 1,
    ofertas: [],
    ...extra,
  };
}

const de = (sku: string, hijo: string, personaje: string, itemId = sku) =>
  linea({ item_id: itemId, hijo, producto_elegido: producto({ sku, personaje }) });

test("la franja Fan junta los productos del personaje, sin repetir ni incluir descartados", () => {
  const spidey = (sku: string, extra: Partial<LineaKit> = {}) =>
    linea({ item_id: sku, producto_elegido: producto({ sku, personaje: "Spiderman" }), ...extra });
  const lineas = [
    spidey("A"),
    spidey("A"),
    spidey("B"),
    spidey("C", { descartado: true }),
    linea({ item_id: "neutro", producto_elegido: producto({ sku: "N", personaje: null }) }),
  ];
  assert.deepEqual(
    productosDelPersonaje(lineas).map((l) => l.producto_elegido?.sku),
    ["A", "B"],
  );
  assert.deepEqual(personajesDelKit(lineas), ["Spiderman"]);
});

test("con los personajes pedidos por hijo, cada hijo solo muestra el suyo", () => {
  const lineas = [
    de("S", "hijo-1", "Spider-Man"),
    de("M", "hijo-2", "Minnie"),
    de("B", "hijo-1", "Bluey"),
    de("M2", "hijo-1", "Minnie"),
  ];
  const pedidos = { "hijo-1": ["spiderman"], "hijo-2": ["minnie"] };
  assert.deepEqual(
    productosDelPersonaje(lineas, pedidos).map((l) => l.producto_elegido?.sku),
    ["S", "M"],
  );
  assert.equal(productosDelPersonaje(lineas).length, 4);
  assert.deepEqual(
    personajesPorHijo(lineas, pedidos).map((g) => [g.hijo, g.personaje, g.lineas.length]),
    [
      ["hijo-1", "Spider-Man", 1],
      ["hijo-2", "Minnie", 1],
    ],
  );
});

test("un producto compartido entre hermanos aparece en el grupo de cada hijo", () => {
  const lineas = [
    de("CART", "hijo-1", "Spiderman", "hijo-1-CART"),
    de("CUAD", "hijo-1", "Spiderman", "hijo-1-CUAD"),
    de("CART", "hijo-2", "Spiderman", "hijo-2-CART"),
  ];
  const pedidos = { "hijo-1": ["spiderman"], "hijo-2": ["spiderman"] };
  assert.deepEqual(
    personajesPorHijo(lineas, pedidos).map((g) => [g.hijo, g.lineas.length]),
    [["hijo-1", 2], ["hijo-2", 1]],
  );
});
