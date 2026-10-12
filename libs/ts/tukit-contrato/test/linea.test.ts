// La razon de no cobrar de una linea comprable que quedo en cero unidades.
//
// El optimizador deja en el kit, con cero unidades y un mensaje, la linea que
// otra ya cubre: la herramienta pedida en varias materias ("Ya va en la linea
// 59") o la que se compra junto con la del hermano. Sin esto el acudiente veia
// el producto sin "compramos" y sin explicacion. Correr con:
// `node --test test/linea.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { razonDeNoCobrar } from "../src/linea.ts";
import type { LineaKit } from "../src/contrato.ts";

function linea(extra: Partial<LineaKit>): LineaKit {
  return {
    orden: 64,
    descripcion: "Tijeras",
    tipo: "util",
    estado_resolucion: "RESUELTO_AUTO",
    informativa: false,
    ...extra,
  } as LineaKit;
}

test("una linea que ya va en otra dice donde", () => {
  const juntada = linea({
    unidades_a_comprar: 0,
    mensaje: "Ya va en la linea 59: sirve para todas las materias.",
  });
  assert.equal(razonDeNoCobrar(juntada), "Ya va en la linea 59: sirve para todas las materias.");
});

test("una linea que se compra no tiene razon de no cobrar", () => {
  assert.equal(razonDeNoCobrar(linea({ unidades_a_comprar: 1 })), null);
});
