import { test } from "node:test";
import assert from "node:assert/strict";
import { serializarAtributos } from "../../../libs/ts/tukit-contrato/src/catalogo.ts";
import { filasDeAtributos } from "../src/lib/atributos-editor.ts";

test("pre-puebla todas las claves declaradas por el concepto", () => {
  const grupos = filasDeAtributos({ materias: 3 }, ["materias", "hojas", "rayado"], []);

  assert.deepEqual(grupos.discriminantes, [
    { clave: "materias", valor: "3" },
    { clave: "hojas", valor: "" },
    { clave: "rayado", valor: "" },
  ]);
  assert.deepEqual(grupos.descriptivos, []);
  assert.deepEqual(grupos.libres, []);
});

test("las claves no declaradas caen en 'libres', no se pierden", () => {
  const grupos = filasDeAtributos({ materias: 3, color: "rojo" }, ["materias"], []);

  assert.deepEqual(grupos.discriminantes, [{ clave: "materias", valor: "3" }]);
  assert.deepEqual(grupos.libres, [{ clave: "color", valor: "rojo" }]);
});

test("guardar tipa y descarta filas vacías", () => {
  const grupos = filasDeAtributos({ materias: 3 }, ["materias", "hojas", "rayado"], []);
  const editadas = grupos.discriminantes.map((p) =>
    p.clave === "hojas" ? { ...p, valor: "80" } : p,
  );
  const cuerpo = serializarAtributos([...editadas, ...grupos.descriptivos, ...grupos.libres]);
  assert.deepEqual(cuerpo, { materias: 3, hojas: 80 });
});
