import { test } from "node:test";
import assert from "node:assert/strict";
import { serializarAtributos } from "../../../libs/ts/tukit-contrato/src/catalogo.ts";
import { conCampo, conValor, filasDeAtributos, pareceUrl } from "../src/lib/atributos-editor.ts";

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

test("una dirección de imagen vacía, http o https es válida y el resto no", () => {
  assert.equal(pareceUrl(""), true);
  assert.equal(pareceUrl("   "), true);
  assert.equal(pareceUrl("https://tienda.co/a.jpg"), true);
  assert.equal(pareceUrl("http://tienda.co/a.jpg"), true);
  assert.equal(pareceUrl("ftp://tienda.co/a.jpg"), false);
  assert.equal(pareceUrl("no es una url"), false);
});

test("editar una fila cambia solo esa fila y no muta la original", () => {
  const filas = [
    { clave: "a", valor: "1" },
    { clave: "b", valor: "2" },
  ];
  assert.deepEqual(conValor(filas, 1, "9"), [
    { clave: "a", valor: "1" },
    { clave: "b", valor: "9" },
  ]);
  assert.deepEqual(conCampo(filas, 0, "clave", "z"), [
    { clave: "z", valor: "1" },
    { clave: "b", valor: "2" },
  ]);
  assert.equal(filas[1]!.valor, "2");
});
