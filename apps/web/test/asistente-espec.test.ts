// La lista blanca de componentes del asistente: lo que no encaja no se pinta.
//
// Correr: `node --test test/asistente-espec.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CLAVES_PESO,
  TIPOS_PERMITIDOS,
  prioridadDeOrden,
  textoDelta,
  validarEspec,
} from "../src/components/asistente/espec.ts";

const tarjeta = (sku: string) => ({
  sku,
  nombre: "Cuaderno cuadriculado",
  marca: "Norma",
  nivel: "economico",
  imagen_url: "https://tienda.exito.com/a.jpg",
  precio_unitario: 5000,
});

const cambio = {
  tipo: "PropuestaCambio",
  props: {
    trabajo_id: "t1",
    perfil: "Ahorrador",
    item_id: "i1",
    descripcion: "Cuaderno",
    antes: tarjeta("A"),
    despues: tarjeta("B"),
    unidades: 2,
    delta_cop: -8000,
    aplicable: true,
  },
};

test("una spec bien formada pasa", () => {
  const spec = validarEspec({
    version: 1,
    componentes: [
      { tipo: "TarjetaPersonaje", props: { nombre: "Spiderman", imagen_url: null } },
      { tipo: "SelectorPresupuesto", props: { minimo: 50000, maximo: 3000000, paso: 10000, valor: null } },
      { tipo: "Prioridades", props: { orden: [...CLAVES_PESO] } },
      { tipo: "ResumenRestricciones", props: {} },
      cambio,
    ],
  });
  assert.ok(spec);
  assert.equal(spec.componentes.length, 5);
});

test("un tipo fuera de la lista blanca descarta toda la spec", () => {
  for (const tipo of ["Script", "Html", "Iframe", "PagarOrden"]) {
    assert.equal(validarEspec({ version: 1, componentes: [{ tipo, props: {} }] }), null);
  }
  assert.ok(!TIPOS_PERMITIDOS.includes("Html" as never));
});

test("un solo componente malo invalida el conjunto", () => {
  const spec = {
    version: 1,
    componentes: [{ tipo: "ResumenRestricciones", props: {} }, { tipo: "Prioridades", props: { orden: ["precio"] } }],
  };
  assert.equal(validarEspec(spec), null);
});

test("las prioridades exigen las cuatro claves una sola vez", () => {
  const malo = (orden: string[]) => validarEspec({ version: 1, componentes: [{ tipo: "Prioridades", props: { orden } }] });
  assert.equal(malo(["precio", "precio", "calidad", "personaje"]), null);
  assert.equal(malo(["precio", "marca_exigida", "calidad", "<b>x</b>"]), null);
});

test("una imagen que no es https se pierde, el resto del componente queda", () => {
  const spec = validarEspec({
    version: 1,
    componentes: [{ tipo: "TarjetaPersonaje", props: { nombre: "Bluey", imagen_url: "javascript:alert(1)" } }],
  });
  assert.ok(spec);
  const c = spec.componentes[0]!;
  assert.equal(c.tipo === "TarjetaPersonaje" && c.props.imagen_url, null);
});

test("cifras que no son enteros seguros se rechazan", () => {
  const roto = structuredClone(cambio);
  (roto.props as { delta_cop: unknown }).delta_cop = "-8000";
  assert.equal(validarEspec({ version: 1, componentes: [roto] }), null);
});

test("version distinta, demasiados componentes o forma rara se rechazan", () => {
  assert.equal(validarEspec({ version: 2, componentes: [] }), null);
  assert.equal(validarEspec({ version: 1, componentes: Array(13).fill({ tipo: "ResumenRestricciones", props: {} }) }), null);
  assert.equal(validarEspec("<script>"), null);
  assert.equal(validarEspec(null), null);
});

test("la prioridad que entiende el formulario sale del primer puesto", () => {
  assert.equal(prioridadDeOrden(["precio", "calidad", "marca_exigida", "personaje"]), "precio");
  assert.equal(prioridadDeOrden(["calidad", "precio", "marca_exigida", "personaje"]), "calidad");
  assert.equal(prioridadDeOrden(["personaje", "precio", "calidad", "marca_exigida"]), "equilibrio");
});

test("el texto del delta distingue ahorro, igual y aumento", () => {
  assert.match(textoDelta(-8000), /Ahorras/);
  assert.equal(textoDelta(0), "Cuesta lo mismo");
  assert.match(textoDelta(3000), /más/);
});
