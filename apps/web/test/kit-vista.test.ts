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
  textoDeConsolidacion,
} from "../src/lib/kit-vista.ts";

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
