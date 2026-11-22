import { test } from "node:test";
import assert from "node:assert/strict";
import { fotoDeConsolidacion, textoDeConsolidacion } from "../src/lib/kit-vista.ts";
import type { LineaKit } from "@tukit/contrato";

test("textoDeConsolidacion nombra a los hijos con sus apodos, sin palabras internas", () => {
  const nombres = new Map([["hijo-0", "Ana"], ["hijo-1", "Luis"]]);
  const dos = textoDeConsolidacion(
    { hijos: ["hijo-0", "hijo-1"], demanda_base: 4, unidades_a_comprar: 1 },
    nombres,
    "$ 5.000",
  );
  assert.equal(dos.paraQuienes, "Para Ana y Luis");
  assert.equal(dos.cantidad, "Necesitan 4 unidades en total y compras 1 paquete");
  assert.equal(dos.ahorro, "Ahorras $ 5.000 frente a comprarlos por separado");
  const tres = textoDeConsolidacion(
    { hijos: ["hijo-0", "hijo-1", "hijo-2"], demanda_base: 6, unidades_a_comprar: 2 },
    nombres,
    null,
  );
  assert.equal(tres.paraQuienes, "Para Ana, Luis y Hijo 3");
  assert.equal(tres.cantidad, "Necesitan 6 unidades en total y compras 2 paquetes");
  assert.equal(tres.ahorro, null);
});

test("textoDeConsolidacion aguanta datos incompletos sin frases colgadas", () => {
  const nombres = new Map([["hijo-0", "Ana"]]);
  const base = { demanda_base: 2, unidades_a_comprar: 1 };
  assert.equal(textoDeConsolidacion({ ...base, hijos: [] }, nombres, null).paraQuienes, null);
  assert.equal(
    textoDeConsolidacion({ ...base, hijos: ["hijo-0", "hijo-0"] }, nombres, null).paraQuienes,
    "Para Ana",
  );
  assert.equal(textoDeConsolidacion({ ...base, hijos: ["hijo-0"] }, nombres, null).paraQuienes, "Para Ana");
  assert.equal(
    textoDeConsolidacion({ hijos: ["hijo-0"], demanda_base: 0, unidades_a_comprar: 2 }, nombres, null).cantidad,
    "En total compras 2 paquetes",
  );
  assert.equal(
    textoDeConsolidacion({ hijos: ["hijo-0"], demanda_base: null, unidades_a_comprar: 0 }, nombres, null).cantidad,
    null,
  );
  assert.equal(
    textoDeConsolidacion({ hijos: ["hijo-0"], demanda_base: 1, unidades_a_comprar: 1 }, nombres, null).cantidad,
    "Necesitan 1 unidad en total y compras 1 paquete",
  );
});

test("consolidacion explica el porque", () => {
  const t = textoDeConsolidacion(
    {
      hijos: ["hijo-1", "hijo-2"],
      demanda_base: 2,
      unidades_a_comprar: 1,
      explicacion: "Un empaque de 50 sale mas barato que 2 por separado.",
    },
    new Map([
      ["hijo-1", "Hijo 1"],
      ["hijo-2", "Hijo 2"],
    ]),
    null,
    new Map([
      ["hijo-1", "Séptimo"],
      ["hijo-2", "Jardín"],
    ]),
  );
  assert.equal(t.porque, "Un empaque de 50 sale mas barato que 2 por separado.");
  assert.equal(t.paraQuienes, "Para Hijo 1 (Séptimo) y Hijo 2 (Jardín)");
});

test("sin explicacion ni grados la consolidacion no trae porque y nombra solo por apodo", () => {
  const t = textoDeConsolidacion({ hijos: ["a", "b"] }, new Map([["a", "Ana"], ["b", "Luis"]]), null);
  assert.equal(t.porque, null);
  assert.equal(t.paraQuienes, "Para Ana y Luis");
});

test("la foto de un producto compartido sale de la linea que lo compra", () => {
  const conFoto = (item: string, unidades: number, imagen: string | null) =>
    ({
      item_id: item,
      unidades_a_comprar: unidades,
      producto_elegido: { sku: "S", nombre: "Borrador de Nata", imagen_url: imagen },
    }) as unknown as LineaKit;
  const lineas = [conFoto("b", 0, null), conFoto("a", 1, "https://x/borrador.png")];
  const r = fotoDeConsolidacion(lineas, { producto: "Borrador de Nata" });
  assert.equal(r.imagen_url, "https://x/borrador.png");
  assert.equal(r.linea?.item_id, "a");
  assert.deepEqual(fotoDeConsolidacion(lineas, { producto: "Otro" }), { imagen_url: null, linea: null });
});
