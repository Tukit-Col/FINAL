import { test } from "node:test";
import assert from "node:assert/strict";
import { ABSTENCIONES, gruposFueraDelCarrito } from "../src/lib/kit-vista.ts";

function linea(item_id: string, campos: Record<string, unknown>) {
  return { item_id, descripcion: item_id, estado_resolucion: "RESUELTO_AUTO", ...campos } as never;
}

test("las abstenciones son lo que no se pudo resolver", () => {
  assert.deepEqual([...ABSTENCIONES], ["hueco", "sin_match", "pendiente_revision"]);
});

test("lo comprable y las abstenciones no aparecen fuera del carrito", () => {
  const lineas = [
    linea("a", { tipo: "util" }),
    linea("b", { tipo: "util", estado_resolucion: "HUECO_CATALOGO" }),
    linea("c", { tipo: "util", estado_resolucion: "SIN_MATCH" }),
    linea("d", { tipo: "util", estado_resolucion: "AMBIGUO" }),
  ];
  assert.deepEqual(gruposFueraDelCarrito(lineas), []);
});

test("cada línea cae en su grupo y los grupos salen en el orden de la pantalla", () => {
  const lineas = [
    linea("casa", { tipo: "no_comprar" }),
    linea("cuenta", { tipo: "otro" }),
    linea("uniforme", { tipo: "uniforme" }),
    linea("libro", { tipo: "texto" }),
    linea("colegio", { tipo: "util", informativa: true }),
  ];
  const grupos = gruposFueraDelCarrito(lineas);
  assert.deepEqual(
    grupos.map((g) => [g.clave, g.lineas.map((l) => l.item_id)]),
    [
      ["libros", ["libro"]],
      ["colegio", ["colegio"]],
      ["uniformes", ["uniforme"]],
      ["cuenta", ["cuenta"]],
      ["casa", ["casa"]],
    ],
  );
});

test("un libro de texto sin producto va a libros, y un grupo vacío se omite", () => {
  const grupos = gruposFueraDelCarrito([linea("t", { tipo: "texto" })]);
  assert.deepEqual(grupos.map((g) => g.clave), ["libros"]);
});
