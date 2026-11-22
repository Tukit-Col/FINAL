import { test } from "node:test";
import assert from "node:assert/strict";
import { serializarAtributos } from "../../../libs/ts/tukit-contrato/src/catalogo.ts";
import {
  NO_EXIGIR,
  candidatosDe,
  exigidoDe,
  filasDeExigencia,
  mismosAtributos,
  paresCurados,
  porAgregar,
  valoresDeProductos,
} from "../src/lib/atributos-renglon.ts";

const bitacora = {
  atributos_discriminantes: ["tipo", "tamano", "hojas"],
  atributos_leidos: { tipo: "cartulina", tamano: "octavo" },
  atributos: { tipo: "dibujo", tamano: NO_EXIGIR },
};

test("una fila por atributo leído o curado, en el orden del concepto", () => {
  const filas = filasDeExigencia(bitacora);
  assert.deepEqual(filas, [
    { clave: "tipo", leido: "cartulina", curado: "dibujo", ajena: false, deducido: false },
    { clave: "tamano", leido: "octavo", curado: "*", ajena: false, deducido: false },
  ]);
  assert.deepEqual(porAgregar(filas, bitacora.atributos_discriminantes), ["hojas"]);
});

test("lo exigido: lo curado manda, * lo quita, sin curar vale lo leído", () => {
  const [tipo, tamano] = filasDeExigencia(bitacora);
  assert.equal(exigidoDe(tipo), "dibujo");
  assert.equal(exigidoDe(tamano), null);
  assert.equal(exigidoDe({ ...tamano, curado: null }), "octavo");
  assert.equal(exigidoDe({ ...tamano, curado: "  " }), "octavo");
});

test("lo deducido (el «más de uno» de una caja) se marca, lo leído del texto no", () => {
  const filas = filasDeExigencia({
    atributos_discriminantes: ["unidades", "color"],
    atributos_leidos: { unidades: 2, color: "rojo" },
    atributos_deducidos: ["unidades"],
    atributos: {},
  });
  assert.deepEqual(
    filas.map((f) => [f.clave, f.deducido]),
    [
      ["unidades", true],
      ["color", false],
    ],
  );
});

test("lo curado con una clave que el concepto no filtra sale aparte y no exige", () => {
  const filas = filasDeExigencia({
    atributos_discriminantes: ["rayado"],
    atributos_leidos: {},
    atributos: { color: "rojo" },
  });
  assert.deepEqual(filas, [{ clave: "color", leido: null, curado: "rojo", ajena: true, deducido: false }]);
  assert.equal(exigidoDe(filas[0]), null);
});

test("guardar manda solo lo curado, tipado, con el * tal cual", () => {
  const filas = [
    ...filasDeExigencia(bitacora),
    { clave: "hojas", leido: null, curado: "15", ajena: false, deducido: false },
    { clave: "gramaje", leido: "40 g", curado: null, ajena: false, deducido: false },
  ];
  const cuerpo = serializarAtributos(paresCurados(filas));
  assert.deepEqual(cuerpo, { tipo: "dibujo", tamano: "*", hojas: 15 });
});

test("sin cambios no se manda nada: la comparación ignora el orden", () => {
  const cuerpo = serializarAtributos(paresCurados(filasDeExigencia(bitacora)));
  assert.ok(mismosAtributos(cuerpo, { tamano: "*", tipo: "dibujo" }));
  assert.ok(!mismosAtributos(cuerpo, { tipo: "dibujo" }));
  assert.ok(!mismosAtributos({ hojas: 100 }, { hojas: "100" }));
});

test("sugiere los valores que declaran los productos del concepto", () => {
  const valores = valoresDeProductos([
    {
      codigo: "C003",
      atributos_discriminantes: ["tipo", "hojas"],
      productos: [
        { atributos: { tipo: "dibujo", hojas: 20, marca: "x" } },
        { atributos: { tipo: "cartulina", hojas: 100 } },
        { atributos: { tipo: "dibujo" } },
      ],
    },
    { codigo: "C999", atributos_discriminantes: ["color"], productos: [{ atributos: {} }] },
  ]);
  assert.deepEqual(valores, { C003: { tipo: ["cartulina", "dibujo"], hojas: ["20", "100"] } });
});

test("las candidatas de un ítem son las suyas por id o, sin id, por el texto de origen", () => {
  const item = { id: "i1", texto_original: "Lápiz HB" };
  const propuestas = [
    { item_id: "i1", texto_origen: "otro" },
    { item_id: "i2", texto_origen: "Lápiz HB" },
    { item_id: null, texto_origen: "Lápiz HB" },
    { item_id: null, texto_origen: "Borrador" },
  ];
  assert.deepEqual(candidatosDe(item, propuestas), [propuestas[0], propuestas[2]]);
});
