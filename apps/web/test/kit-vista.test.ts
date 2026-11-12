// Las reglas puras de lo que el renglón del kit le muestra al acudiente: a qué
// hijo pertenece (su apodo, nunca la referencia interna) y en qué tienda está
// el precio.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/kit-vista.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { etiquetasDeHijos, pistaDeTienda } from "../src/lib/kit-vista.ts";

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
