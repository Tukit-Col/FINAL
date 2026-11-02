// Lo que el acudiente lee donde antes habia un "$ 0": cada linea dice si se
// cobra o por que no y donde se consigue; los libros y uniformes se distinguen;
// la franja Fan junta los productos del personaje; la contrasena muestra sus
// reglas antes de escribirla. Correr con `node --test test/presentacion.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  claveValida,
  dondeComprar,
  esLibro,
  esUniforme,
  estadoDePrecio,
  etiquetaEmpaque,
  lineasQueSuman,
  personajesDelKit,
  productosDelPersonaje,
  reglasDeClave,
  hayQueCobrar,
} from "../src/linea.ts";
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

test("una linea con subtotal real muestra su precio", () => {
  assert.deepEqual(estadoDePrecio(linea({})), { tipo: "precio", valor: 9000 });
});

test("una linea comprable en cero nunca muestra 0: dice que no tiene precio y donde comprarla", () => {
  const sinPrecio = linea({
    subtotal_linea: 0,
    producto_elegido: producto({ ofertas: [{ tienda: "Panamericana", precio: 0, vigente_hasta: null }] }),
  });
  assert.deepEqual(estadoDePrecio(sinPrecio), {
    tipo: "sin_cobro",
    titulo: "Sin precio aún — se compra en Panamericana",
  });
  const sinNada = linea({ subtotal_linea: null });
  assert.deepEqual(estadoDePrecio(sinNada), { tipo: "sin_cobro", titulo: "Sin precio aún" });
});

test("el catalogo manda: si dice donde se compra, esa tienda gana", () => {
  const l = linea({
    subtotal_linea: null,
    se_compra_en: "Librería Nacional",
    producto_elegido: producto({ ofertas: [{ tienda: "Otra", precio: 1, vigente_hasta: null }] }),
  });
  assert.equal(dondeComprar(l), "Librería Nacional");
});

test("lo que entrega el colegio, las licencias y los uniformes dicen como conseguirlos", () => {
  const colegio = linea({ informativa: true, subtotal_linea: null });
  assert.equal(estadoDePrecio(colegio).tipo === "sin_cobro" && estadoDePrecio(colegio).titulo, "Lo entrega el colegio");

  const licencia = linea({
    tipo: "licencia_digital",
    informativa: true,
    subtotal_linea: null,
    url_externa: "https://www.quovix.com/comprar",
  });
  const e = estadoDePrecio(licencia);
  assert.equal(e.tipo === "sin_cobro" && e.titulo, "Licencia digital: se compra en quovix.com");

  const uniforme = linea({ tipo: "uniforme", subtotal_linea: null, se_compra_en: "Uniformes Lupita" });
  const u = estadoDePrecio(uniforme);
  assert.equal(u.tipo === "sin_cobro" && u.titulo, "Uniforme: se compra en Uniformes Lupita");
});

test("un libro de texto dice la editorial y un uniforme se reconoce como tal", () => {
  const libro = linea({
    tipo: "texto",
    informativa: true,
    subtotal_linea: null,
    edicion: { isbn13: "1", titulo: "Matemáticas 4", editorial: "Santillana", anio_edicion: 2026 },
  });
  assert.equal(esLibro(libro), true);
  assert.equal(esUniforme(libro), false);
  const e = estadoDePrecio(libro);
  assert.equal(e.tipo === "sin_cobro" && e.titulo, "Libro: se compra en Santillana");
  assert.equal(esUniforme(linea({ tipo: "uniforme" })), true);
});

test("una linea descartada dice cuanto se ahorra y no cuenta en el total", () => {
  const descartada = linea({ descartado: true, subtotal_linea: null, subtotal_descartado: 9000 });
  assert.deepEqual(estadoDePrecio(descartada), { tipo: "descartado", ahorro: 9000 });
  assert.deepEqual(lineasQueSuman([linea({}), descartada]).length, 1);
});

test("un total en cero no se cobra ni se muestra como $ 0", () => {
  assert.equal(hayQueCobrar(0), false);
  assert.equal(hayQueCobrar(null), false);
  assert.equal(hayQueCobrar(18900), true);
});

test("el empaque se dice como empaque", () => {
  assert.equal(etiquetaEmpaque(12, 1), "Empaque de 12");
  assert.equal(etiquetaEmpaque(1, 1), "Por unidad");
  assert.equal(etiquetaEmpaque(12, 2), "Empaque de 12 · compras 2");
});

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

test("las reglas de la contrasena se conocen antes de escribir y se marcan al cumplirse", () => {
  const vacia = reglasDeClave("");
  assert.equal(vacia.length >= 1, true);
  assert.equal(vacia.every((r) => r.cumple === false), true);
  assert.match(vacia[0]!.texto, /8 caracteres/);
  assert.equal(claveValida("corta"), false);
  assert.equal(claveValida("larguisima1"), true);
});
