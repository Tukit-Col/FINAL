import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CLAVE_RESTRICCIONES,
  aplicarPersonajes,
  cambiosDelAsistente,
  filtrosDePreferencias,
  leerRestriccionesGuardadas,
} from "../src/lib/restricciones-asistente.ts";

const pesos = { precio: 0.4, marca_exigida: 0.2, calidad: 0.3, personaje: 0.1 };

test("personajes, tope y prioridad se traducen a los campos del formulario", () => {
  const cambios = cambiosDelAsistente({
    personajes: ["Spiderman", " Frozen ", "Spiderman", ""],
    presupuesto_por_hijo: 300000,
    prioridad: "equilibrio",
    pesos,
    disposicion_sobreprecio: 0.05,
  });
  assert.deepEqual(cambios, {
    personajes: "Spiderman, Frozen",
    prioridad: "equilibrio",
    presupuesto: "300000",
    marcasExcluidas: [],
    soloDisponibles: false,
  });
});

test("un tope fuerza el punto medio, que es donde el formulario lo usa (conTope)", () => {
  const cambios = cambiosDelAsistente({ personajes: [], presupuesto_por_hijo: 250000.4, prioridad: "precio", pesos });
  assert.equal(cambios?.prioridad, "equilibrio");
  assert.equal(cambios?.presupuesto, "250000");
});

test("sin tope, la prioridad del asistente se respeta y el campo de tope queda vacio", () => {
  const cambios = cambiosDelAsistente({ personajes: [], presupuesto_por_hijo: null, prioridad: "calidad", pesos });
  assert.deepEqual(cambios, {
    personajes: null,
    prioridad: "calidad",
    presupuesto: "",
    marcasExcluidas: [],
    soloDisponibles: false,
  });
});

test("lo invalido se ignora y un payload vacio no cambia nada", () => {
  assert.equal(cambiosDelAsistente(null), null);
  assert.equal(cambiosDelAsistente("x"), null);
  assert.equal(cambiosDelAsistente({ personajes: [3], presupuesto_por_hijo: -5, prioridad: "lujo" }), null);
});

test("los personajes solo van a los hijos que no tenian, sin pisar lo escrito", () => {
  const hijos = [{ personajes: "" }, { personajes: "Bluey" }];
  assert.deepEqual(aplicarPersonajes(hijos, "Spiderman"), [{ personajes: "Spiderman" }, { personajes: "Bluey" }]);
  assert.deepEqual(aplicarPersonajes(hijos, null), hijos);
});

test("sessionStorage roto o ausente no lanza", () => {
  assert.equal(leerRestriccionesGuardadas(undefined), null);
  assert.equal(leerRestriccionesGuardadas({ getItem: () => "{no es json" }), null);
  const guardado = { personajes: ["Frozen"] };
  assert.deepEqual(
    leerRestriccionesGuardadas({ getItem: (k: string) => (k === CLAVE_RESTRICCIONES ? JSON.stringify(guardado) : null) }),
    guardado,
  );
});

test("las marcas excluidas y solo_disponibles pasan al formulario, validados", () => {
  const cambios = cambiosDelAsistente({
    marcas_excluidas: [" Faber-Castell ", "Norma", "Norma", 7, "", "x".repeat(41)],
    solo_disponibles: true,
  });
  assert.deepEqual(cambios?.marcasExcluidas, ["Faber-Castell", "Norma"]);
  assert.equal(cambios?.soloDisponibles, true);
});

test("un payload que solo trae filtros ya es utilizable", () => {
  assert.notEqual(cambiosDelAsistente({ marcas_excluidas: ["Norma"] }), null);
  assert.notEqual(cambiosDelAsistente({ solo_disponibles: true }), null);
});

test("solo_disponibles exige un true de verdad y las marcas se acotan a 10", () => {
  assert.equal(cambiosDelAsistente({ solo_disponibles: "true", personajes: ["Bluey"] })?.soloDisponibles, false);
  const muchas = Array.from({ length: 30 }, (_, i) => `m${i}`);
  assert.equal(cambiosDelAsistente({ marcas_excluidas: muchas })?.marcasExcluidas.length, 10);
});

test("filtrosDePreferencias solo incluye lo activo, para no cambiar las preferencias de siempre", () => {
  assert.deepEqual(filtrosDePreferencias([], false), {});
  assert.deepEqual(filtrosDePreferencias(["Norma"], false), { marcas_excluidas: ["Norma"] });
  assert.deepEqual(filtrosDePreferencias([], true), { solo_disponibles: true });
});
