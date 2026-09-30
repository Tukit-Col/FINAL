// Prueba de la lógica pura del editor de atributos (Task D2). `apps/admin` no
// tiene runner de componentes, así que se prueba la función de mapeo extraída
// (que es donde vivía el bug: pre-poblar las claves del concepto y tipar al
// guardar), corriéndola con `node --test` (Node 24 hace type-stripping nativo).
//
// Vive en `test/` (fuera de `src/`) para que el `tsc` de `next build` no la
// compile: usa imports con extensión `.ts` que `node --test` exige pero el
// build de Next rechaza, mismo patrón que `libs/ts/tukit-contrato/test`.
//
// Correr:  node --test test/atributos-editor.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
// Import directo a los fuentes con extensión: el loader ESM crudo de
// `node --test` no resuelve el barrel `@tukit/contrato` (imports extensionless)
// ni el alias `@/`. Next sí (vía tsconfig); aquí solo se prueba lógica pura.
import { serializarAtributos } from "../../../libs/ts/tukit-contrato/src/catalogo.ts";
import { filasDeAtributos } from "../src/lib/atributos-editor.ts";

// El caso del screenshot (Review Focus #4): un cuaderno C001 con solo `materias`
// mientras el concepto declara `materias`/`hojas`/`rayado`. El editor debe
// montar filas para las tres —las que el producto trae con su valor, las que no
// vacías— repartidas por grupo (discriminantes vs descriptivos).
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

// Una clave que el producto trae pero el concepto NO declara sigue apareciendo,
// en el grupo de claves libres (no se pierde al editar).
test("las claves no declaradas caen en 'libres', no se pierden", () => {
  const grupos = filasDeAtributos({ materias: 3, color: "rojo" }, ["materias"], []);

  assert.deepEqual(grupos.discriminantes, [{ clave: "materias", valor: "3" }]);
  assert.deepEqual(grupos.libres, [{ clave: "color", valor: "rojo" }]);
});

// Al guardar, `serializarAtributos` (contrato, Task C5) tipa los valores y
// descarta las filas vacías: llenar solo `hojas=80` sobre el caso del
// screenshot manda `{materias: 3, hojas: 80}` tipado, `rayado` (vacío) no se
// afirma.
test("guardar tipa y descarta filas vacías", () => {
  const grupos = filasDeAtributos({ materias: 3 }, ["materias", "hojas", "rayado"], []);
  // La persona escribe 80 en la fila `hojas`, deja `rayado` vacía.
  const editadas = grupos.discriminantes.map((p) =>
    p.clave === "hojas" ? { ...p, valor: "80" } : p,
  );
  const cuerpo = serializarAtributos([...editadas, ...grupos.descriptivos, ...grupos.libres]);
  assert.deepEqual(cuerpo, { materias: 3, hojas: 80 });
});
