// Las reglas puras de lo que el renglón del kit le muestra al acudiente: a qué
// hijo pertenece (su apodo, nunca la referencia interna) y en qué tienda está
// el precio.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/kit-vista.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  etiquetasDeHijos,
  gradosDeHijos,
  notaSinEncaje,
  pistaDeTienda,
  resumenPorHijo,
  textoDeConsolidacion,
  fotoDeConsolidacion,
} from "../src/lib/kit-vista.ts";
import type { LineaKit } from "@tukit/contrato";

const COLEGIO = "4c06f0e5-cb44-5865-93e5-ea7b2f115d49";
const OTRO = "2030c794-3ff4-5b1a-a2ec-5c5d383de3f1";

test("la ruta rápida («canonico») muestra el apodo del hijo de la cuenta", () => {
  const etiquetas = etiquetasDeHijos(
    ["canonico", "canonico"],
    [{ colegio_id: COLEGIO, grado: "Primero" }],
    [{ colegio_id: COLEGIO, grado: "Primero", apodo: "Tomasito" }],
  );
  assert.equal(etiquetas.get("canonico"), "Tomasito");
});

test("el apodo guardado en el trabajo sale aunque las matriculas no carguen (identidad caida)", () => {
  // Ruta rapida: las lineas dicen "canonico" y el trabajo trae un solo hijo con su
  // apodo. Sin matriculas (fallo o 429 -> []), el kit igual lo nombra.
  const etiquetas = etiquetasDeHijos(
    ["canonico", "canonico"],
    [{ colegio_id: COLEGIO, grado: "Primero", apodo: "Tomi" }],
    [],
  );
  assert.equal(etiquetas.get("canonico"), "Tomi");
});

test("dos hermanos en el mismo grado se nombran por su apodo del trabajo, no por matriculas", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-1", "hijo-2"],
    [
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Jardin", apodo: "Sofi" },
      { referencia: "hijo-2", colegio_id: COLEGIO, grado: "Jardin", apodo: "Luca" },
    ],
    [
      { colegio_id: COLEGIO, grado: "Jardin", apodo: "Sofi" },
      { colegio_id: COLEGIO, grado: "Jardin", apodo: "Luca" },
    ],
  );
  assert.equal(etiquetas.get("hijo-1"), "Sofi");
  assert.equal(etiquetas.get("hijo-2"), "Luca");
});

test("un hijo sin apodo, solo en el kit, no lleva pastilla", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-0"],
    [{ referencia: "hijo-0", colegio_id: COLEGIO, grado: "Primero" }],
    [{ colegio_id: COLEGIO, grado: "Primero", apodo: null }],
  );
  assert.equal(etiquetas.get("hijo-0"), undefined);
});

test("sin sesión (sin matrículas) tampoco aparece la referencia", () => {
  const etiquetas = etiquetasDeHijos(["canonico"], [{ colegio_id: COLEGIO, grado: "Primero" }]);
  assert.equal(etiquetas.size, 0);
});

test("con dos hijos, el que no tiene apodo se llama «Hijo N»", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-1", "hijo-2", "hijo-1"],
    [
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Primero" },
      { referencia: "hijo-2", colegio_id: OTRO, grado: "Noveno" },
    ],
    [
      { colegio_id: COLEGIO, grado: "Primero", apodo: "Sofi" },
      { colegio_id: OTRO, grado: "Noveno", apodo: "  " },
    ],
  );
  assert.equal(etiquetas.get("hijo-1"), "Sofi");
  assert.equal(etiquetas.get("hijo-2"), "Hijo 2");
});

test("dos matrículas del mismo colegio y grado con apodos distintos no adivinan", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-0"],
    [{ referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero" }],
    [
      { colegio_id: COLEGIO, grado: "Tercero", apodo: "Pipe" },
      { colegio_id: COLEGIO, grado: "Tercero", apodo: "Juanchi" },
    ],
  );
  assert.equal(etiquetas.get("hijo-0"), undefined);
});

test("dos hijos mismo colegio y grado con apodos distintos", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-0", "hijo-1"],
    [
      { referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero", apodo: "Sofía" },
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Tercero", apodo: "Lucía" },
    ],
  );
  assert.deepEqual([...etiquetas], [
    ["hijo-0", "Sofía"],
    ["hijo-1", "Lucía"],
  ]);
});

test("un solo apodo en matrículas ya no se aplica a ambos hermanos", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-0", "hijo-1"],
    [
      { referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero" },
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Tercero" },
    ],
    [{ colegio_id: COLEGIO, grado: "Tercero", apodo: "Sofía" }],
  );
  assert.equal(etiquetas.get("hijo-0"), "Hijo 1");
  assert.equal(etiquetas.get("hijo-1"), "Hijo 2");
});

test("el apodo del hijo gana a las matrículas; sin él se cae a ellas", () => {
  const matriculas = [{ colegio_id: COLEGIO, grado: "Tercero", apodo: "Pipe" }];
  const gana = etiquetasDeHijos(
    ["hijo-0"],
    [{ referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero", apodo: " Tomás " }],
    matriculas,
  );
  assert.equal(gana.get("hijo-0"), "Tomás");
  const cae = etiquetasDeHijos(
    ["hijo-0"],
    [{ referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero", apodo: "  " }],
    matriculas,
  );
  assert.equal(cae.get("hijo-0"), "Pipe");
});

test("un hermano con apodo junto a otro sin apodo: «Sofía» y «Hijo 2»", () => {
  const etiquetas = etiquetasDeHijos(
    ["hijo-0", "hijo-1"],
    [
      { referencia: "hijo-0", colegio_id: COLEGIO, grado: "Tercero", apodo: "Sofía" },
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Tercero" },
    ],
  );
  assert.equal(etiquetas.get("hijo-0"), "Sofía");
  assert.equal(etiquetas.get("hijo-1"), "Hijo 2");
});

test("ninguna etiqueta es una referencia interna", () => {
  const referencias = ["canonico", "hijo-0", "hijo-1"];
  const etiquetas = etiquetasDeHijos(referencias, [], []);
  for (const valor of etiquetas.values()) {
    assert.ok(!referencias.includes(valor), `se coló la referencia ${valor}`);
  }
});

test("sin nombre de tienda no queda un «en» colgando", () => {
  assert.equal(pistaDeTienda([]), null);
  assert.equal(pistaDeTienda([{ tienda: "" }]), null);
  assert.equal(pistaDeTienda([{ tienda: "   " }]), null);
});

test("con tienda dice dónde, y cuántas si hay varias", () => {
  assert.equal(pistaDeTienda([{ tienda: "Éxito" }]), "en Éxito");
  assert.equal(pistaDeTienda([{ tienda: "" }, { tienda: "Panamericana" }]), "en Panamericana");
  assert.equal(
    pistaDeTienda([{ tienda: "Éxito" }, { tienda: "Panamericana" }, { tienda: "" }]),
    "en Éxito · 2 tiendas",
  );
});

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
  // Tres hijos y uno sin apodo: "Hijo N" por su lugar; sin ahorro no se inventa.
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
  // Sin hijos: no queda un "Para " suelto.
  assert.equal(textoDeConsolidacion({ ...base, hijos: [] }, nombres, null).paraQuienes, null);
  // Hijo repetido: se nombra una vez.
  assert.equal(
    textoDeConsolidacion({ ...base, hijos: ["hijo-0", "hijo-0"] }, nombres, null).paraQuienes,
    "Para Ana",
  );
  // Un solo hijo.
  assert.equal(textoDeConsolidacion({ ...base, hijos: ["hijo-0"] }, nombres, null).paraQuienes, "Para Ana");
  // Demanda 0 o nula: se omite la frase de cantidad que no existe.
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

test("consolidacion sin explicacion ni grados queda como antes", () => {
  const t = textoDeConsolidacion({ hijos: ["a", "b"] }, new Map([["a", "Ana"], ["b", "Luis"]]), null);
  assert.equal(t.porque, null);
  assert.equal(t.paraQuienes, "Para Ana y Luis");
});

test("la nota de un ancla sin encaje dice que util y que personaje", () => {
  assert.equal(
    notaSinEncaje({ concepto: "C001", personaje: "spiderman" }),
    "No encontramos cuaderno de Spiderman que cumpla lo que pide la lista; dejamos uno sin personaje.",
  );
  assert.equal(
    notaSinEncaje({ concepto: "C999", personaje: "minnie" }),
    "No encontramos producto de Minnie que cumpla lo que pide la lista; dejamos uno sin personaje.",
  );
});

test("el grado de cada hijo sale de su referencia; la ruta rapida usa el unico hijo", () => {
  const dos = gradosDeHijos(
    ["hijo-1", "hijo-2"],
    [
      { referencia: "hijo-1", colegio_id: COLEGIO, grado: "Séptimo" },
      { referencia: "hijo-2", colegio_id: COLEGIO, grado: "Jardín" },
    ],
  );
  assert.deepEqual([...dos], [["hijo-1", "Séptimo"], ["hijo-2", "Jardín"]]);
  const rapida = gradosDeHijos(["canonico"], [{ colegio_id: COLEGIO, grado: "Primero" }]);
  assert.equal(rapida.get("canonico"), "Primero");
});


// --- resumenPorHijo (panel por hijo) ------------------------------------------

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
  assert.equal(b.productos.length, 0); // su cartuchera consolidada-en-cero no se repite
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


// --- Arreglos de la revision del panel por hijo ---------------------------------

test("los totales por hijo suman el total del kit, incluso con renglones en revision", () => {
  const kit = {
    lineas: [
      ln("a", { descripcion: "cuaderno", subtotal_linea: 5000 }),
      // Ambiguo con precio: el backend lo suma al total del kit.
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
  // Con un solo hijo real, la linea suelta es de el.
  const uno = resumenPorHijo({ lineas: [sinHijo, ln("a")], consolidaciones: [] }, MAPA([]), MAPA([]), undefined);
  assert.deepEqual(uno.map((x) => [x.hijo, x.total]), [["a", 2000]]);
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
