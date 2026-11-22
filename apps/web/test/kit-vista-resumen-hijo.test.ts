import { test } from "node:test";
import assert from "node:assert/strict";
import { resumenPorHijo } from "../src/lib/kit-vista.ts";
import type { LineaKit } from "@tukit/contrato";

function ln(hijo: string, extra: Partial<LineaKit> = {}): LineaKit {
  return {
    item_id: `${hijo}-${extra.descripcion ?? "x"}`,
    hijo,
    descripcion: "Cuaderno",
    tipo: "util",
    estado_resolucion: "RESUELTO_AUTO",
    informativa: false,
    unidades_a_comprar: 1,
    subtotal_linea: 1000,
    producto_elegido: { sku: "N", nombre: "neutro", marca: null, nivel: "confiable", personaje: null, imagen_url: null },
    ...extra,
  } as LineaKit;
}

const MAPA = (pares: [string, string][]) => new Map(pares);

test("resumen agrupa por hijo en orden de aparicion con nombre, grado y personaje", () => {
  const kit = {
    lineas: [ln("b", { descripcion: "p" }), ln("a", { descripcion: "q" }), ln("a", { descripcion: "r" })],
    consolidaciones: [],
  };
  const r = resumenPorHijo(
    kit,
    MAPA([["a", "Ana"], ["b", "Luis"]]),
    MAPA([["a", "Séptimo"], ["b", "Jardín"]]),
    { a: ["Spider-Man"], b: ["Minnie"] },
  );
  assert.deepEqual(r.map((x) => x.hijo), ["b", "a"]);
  const a = r.find((x) => x.hijo === "a")!;
  assert.deepEqual([a.nombre, a.grado, a.personaje], ["Ana", "Séptimo", "Spider-Man"]);
});

test("el total suma subtotales y el consolidado-en-cero no se duplica como producto", () => {
  const compartido = { sku: "CART", nombre: "Cartuchera", marca: null, nivel: "confiable", personaje: null, imagen_url: null };
  const kit = {
    lineas: [
      ln("a", { descripcion: "cart", producto_elegido: compartido, unidades_a_comprar: 1, subtotal_linea: 9000 }),
      ln("a", { descripcion: "otro", subtotal_linea: 2000 }),
      ln("b", { descripcion: "cart", producto_elegido: compartido, unidades_a_comprar: 0, subtotal_linea: 0 }),
    ],
    consolidaciones: [{ concepto: "C009", hijos: ["a", "b"], demanda_base: 2, producto: "Cartuchera", unidades_a_comprar: 1, ahorro: { monto: 0 } as never, explicacion: "" }],
  };
  const r = resumenPorHijo(kit as never, MAPA([["a", "Ana"], ["b", "Luis"]]), MAPA([]), undefined);
  const b = r.find((x) => x.hijo === "b")!;
  assert.equal(b.productos.length, 0);
  assert.equal(b.total, 0);
  assert.equal(r.find((x) => x.hijo === "a")!.comparten, 1);
  assert.equal(b.comparten, 1);
});

test("hijo sin personaje no trae personaje ni nota de falta", () => {
  const kit = { lineas: [ln("a"), ln("b")], consolidaciones: [] };
  const r = resumenPorHijo(kit, MAPA([["a", "Ana"], ["b", "Luis"]]), MAPA([]), { a: ["spiderman"] });
  const b = r.find((x) => x.hijo === "b")!;
  assert.equal(b.personaje, null);
  assert.deepEqual(b.falta, []);
});

test("falta lista personaje_sin_encaje y las abstenciones", () => {
  const kit = {
    lineas: [
      ln("a", { descripcion: "cuaderno" }),
      ln("a", { descripcion: "regla que no existe", estado_resolucion: "HUECO_CATALOGO", producto_elegido: null, subtotal_linea: null }),
    ],
    consolidaciones: [],
    personaje_sin_encaje: [{ hijo: "a", concepto: "C001", personaje: "spiderman" }],
  };
  const r = resumenPorHijo(kit, MAPA([["a", "Ana"]]), MAPA([]), { a: ["spiderman"] });
  const a = r[0];
  assert.equal(a.falta.length, 2);
  assert.ok(a.falta.some((f) => f.includes("Spiderman")));
  assert.ok(a.falta.some((f) => f.includes("regla que no existe")));
});

test("con un solo hijo devuelve un solo resumen", () => {
  const kit = { lineas: [ln("a"), ln("a", { descripcion: "y" })], consolidaciones: [] };
  assert.equal(resumenPorHijo(kit, MAPA([["a", "Ana"]]), MAPA([]), undefined).length, 1);
});

test("los totales por hijo suman el total del kit, incluso con renglones en revision", () => {
  const kit = {
    lineas: [
      ln("a", { descripcion: "cuaderno", subtotal_linea: 5000 }),
      ln("a", { descripcion: "regla", estado_resolucion: "AMBIGUO", subtotal_linea: 3000 }),
      ln("b", { descripcion: "lapiz", subtotal_linea: 2000 }),
      ln("b", { descripcion: "libro", informativa: true, subtotal_linea: null, producto_elegido: null }),
      ln("a", { descripcion: "ya lo tengo", descartado: true, subtotal_linea: null }),
    ],
    consolidaciones: [],
  };
  const r = resumenPorHijo(kit, MAPA([["a", "Ana"], ["b", "Luis"]]), MAPA([]), undefined);
  assert.equal(r.reduce((n, x) => n + x.total, 0), 10000);
  assert.ok(r.find((x) => x.hijo === "a")!.falta.some((f) => f.includes("regla")));
});

test("un mismo producto en varios renglones de un hijo sale una vez con su cantidad", () => {
  const kit = {
    lineas: [ln("a", { descripcion: "c1" }), ln("a", { descripcion: "c2" }), ln("a", { descripcion: "c3" }), ln("b")],
    consolidaciones: [],
  };
  const a = resumenPorHijo(kit, MAPA([["a", "Ana"], ["b", "Luis"]]), MAPA([]), undefined)[0];
  assert.equal(a.productos.length, 1);
  assert.equal(a.veces["N"], 3);
});

test("un hijo con solo renglones que van por fuera cuenta cuantos son", () => {
  const kit = {
    lineas: [
      ln("a"),
      ln("b", { descripcion: "texto", informativa: true, subtotal_linea: null, producto_elegido: null }),
      ln("b", { descripcion: "uniforme", tipo: "uniforme", subtotal_linea: null, producto_elegido: null }),
    ],
    consolidaciones: [],
  };
  const b = resumenPorHijo(kit, MAPA([["a", "Ana"], ["b", "Luis"]]), MAPA([]), undefined)[1];
  assert.equal(b.productos.length, 0);
  assert.equal(b.aparte, 2);
});

test("las lineas sin hijo no crean un hijo fantasma", () => {
  const sinHijo = ln("x", { descripcion: "suelta" });
  delete (sinHijo as { hijo?: string }).hijo;
  const dos = resumenPorHijo(
    { lineas: [sinHijo, ln("a"), ln("b")], consolidaciones: [] },
    MAPA([["a", "Ana"], ["b", "Luis"]]),
    MAPA([]),
    undefined,
  );
  assert.deepEqual(dos.map((x) => x.hijo), ["a", "b"]);
  const uno = resumenPorHijo({ lineas: [sinHijo, ln("a")], consolidaciones: [] }, MAPA([]), MAPA([]), undefined);
  assert.deepEqual(uno.map((x) => [x.hijo, x.total]), [["a", 2000]]);
});

test("el numero por hijo cuenta renglones de su lista, igual en todos los kits", () => {
  const l = (item: string, sku: string) =>
    ({ item_id: item, hijo: "a", descripcion: "Cuaderno", estado: "RESUELTO_AUTO", informativa: false,
       unidades_a_comprar: 1, subtotal_linea: 1000, producto_elegido: { sku, nombre: sku, precio: 1000 } }) as unknown as LineaKit;
  const nombres = new Map([["a", "Ana"], ["b", "Luis"]]);
  const ahorrador = resumenPorHijo({ lineas: [l("1", "X"), l("2", "X"), l("3", "Y")], consolidaciones: [] }, nombres, new Map());
  const fan = resumenPorHijo({ lineas: [l("1", "X"), l("2", "SPIDER"), l("3", "Y")], consolidaciones: [] }, nombres, new Map());
  assert.equal(ahorrador[0]!.renglones, 3);
  assert.equal(fan[0]!.renglones, 3);
  assert.notEqual(ahorrador[0]!.productos.length, fan[0]!.productos.length);
});
