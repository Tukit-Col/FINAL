import { test } from "node:test";
import assert from "node:assert/strict";
import { etiquetasDeHijos, gradosDeHijos } from "../src/lib/kit-vista.ts";

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

test("sin matriculas, el apodo guardado en el trabajo nombra al hijo", () => {
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

test("dos hijos del mismo colegio y grado se nombran cada uno por su apodo", () => {
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

test("un único apodo en matrículas no se reparte entre dos hermanos del mismo grado", () => {
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
