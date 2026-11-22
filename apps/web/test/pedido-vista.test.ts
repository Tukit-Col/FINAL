import { test } from "node:test";
import assert from "node:assert/strict";
import { agruparLineas, diaBogota, fechaHoraBogota } from "../src/lib/pedido-vista.ts";

const linea = (sku: string, cantidad: number, precio_unitario: number) => ({
  sku,
  nombre: `Producto ${sku}`,
  cantidad,
  precio_unitario,
});

test("el mismo producto de dos hijos se suma en una fila", () => {
  const filas = agruparLineas([linea("A", 1, 4500), linea("B", 2, 1000), linea("A", 2, 4500)]);
  assert.deepEqual(
    filas.map((f) => [f.nombre, f.cantidad, f.precioUnitario, f.subtotal]),
    [
      ["Producto A", 3, 4500, 13500],
      ["Producto B", 2, 1000, 2000],
    ],
  );
});

test("dos precios congelados del mismo sku no se mezclan", () => {
  const filas = agruparLineas([linea("A", 1, 4500), linea("A", 1, 5000)]);
  assert.equal(filas.length, 2);
});

test("sin lineas no hay filas", () => {
  assert.deepEqual(agruparLineas([]), []);
});

test("las fechas se muestran en la hora de Bogota", () => {
  const texto = fechaHoraBogota("2026-10-02T03:30:00+00:00");
  assert.match(texto, /1 de oct/);
  assert.match(texto, /10:30/);
  assert.match(diaBogota("2026-10-02T03:30:00+00:00"), /1 de octubre/);
});
