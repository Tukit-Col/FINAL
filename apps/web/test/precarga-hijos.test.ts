import { test } from "node:test";
import assert from "node:assert/strict";
import { MAX_HIJOS, avisosDePrecarga, precargarHijos } from "../src/lib/precarga-hijos.ts";

const COLEGIOS = [
  { colegio_id: "san-pedro", nombre: "Colegio San Pedro", grados: ["Primero", "Tercero"] },
  { colegio_id: "agustiniano", nombre: "Colegio Agustiniano", grados: ["Jardin", "Tercero"] },
  { colegio_id: "cacs", nombre: "Colegio CACS", grados: [] },
  { colegio_id: "modelia", nombre: "Colegio Modelia", grados: [] },
];

const m = (colegio_id: string, grado: string, apodo: string | null = null) => ({
  colegio_id,
  grado,
  apodo,
});

test("los hijos de colegios sin lista no se precargan vacíos: quedan fuera con su motivo", () => {
  const { precargados, fuera } = precargarHijos(
    [m("cacs", "Quinto", "Pipe"), m("san-pedro", "Primero", "Sofi"), m("modelia", "Tercero")],
    COLEGIOS,
  );
  assert.deepEqual(precargados, [m("san-pedro", "Primero", "Sofi")]);
  assert.deepEqual(fuera, [
    { nombre: "Pipe", colegio: "Colegio CACS", grado: "Quinto", motivo: "sin_lista" },
    { nombre: null, colegio: "Colegio Modelia", grado: "Tercero", motivo: "sin_lista" },
  ]);
});

test("un grado sin lista verificada en un colegio aliado tampoco se precarga", () => {
  const { precargados, fuera } = precargarHijos([m("san-pedro", "Quinto")], COLEGIOS);
  assert.equal(precargados.length, 0);
  assert.equal(fuera[0]?.motivo, "sin_lista");
});

test("nunca precarga más hijos de los que el formulario permite", () => {
  const matriculas = [
    m("san-pedro", "Primero", "A"),
    m("san-pedro", "Tercero", "B"),
    m("agustiniano", "Jardin", "C"),
    m("agustiniano", "Tercero", "D"),
    m("agustiniano", "Tercero", "E"),
  ];
  const { precargados, fuera } = precargarHijos(matriculas, COLEGIOS);
  assert.equal(MAX_HIJOS, 4);
  assert.equal(precargados.length, MAX_HIJOS);
  assert.deepEqual(fuera, [
    { nombre: "E", colegio: "Colegio Agustiniano", grado: "Tercero", motivo: "tope" },
  ]);
});

test("un colegio que no está en la lista no muestra su id", () => {
  const { fuera } = precargarHijos([m("desconocido", "Primero")], COLEGIOS);
  assert.equal(fuera[0]?.colegio, null);
});

test("el aviso explica en palabras de papá qué quedó fuera y qué hacer", () => {
  const avisos = avisosDePrecarga([
    { nombre: "Pipe", colegio: "Colegio CACS", grado: "Quinto", motivo: "sin_lista" },
    { nombre: null, colegio: null, grado: "Tercero", motivo: "sin_lista" },
    { nombre: "E", colegio: "Colegio Agustiniano", grado: "Tercero", motivo: "tope" },
  ]);
  assert.equal(avisos.length, 2);
  assert.match(avisos[0]!, /Pipe \(Colegio CACS · Quinto\)/);
  assert.match(avisos[0]!, /tu hijo de Tercero/);
  assert.match(avisos[0]!, /Agregar otro hijo/);
  assert.match(avisos[1]!, /hasta 4 hijos/);
  assert.match(avisos[1]!, /E \(Colegio Agustiniano · Tercero\)/);
  assert.deepEqual(avisosDePrecarga([]), []);
});

test("con el formulario en el tope de hijos el aviso no manda a «Agregar otro hijo», que se oculta en el tope", () => {
  const avisos = avisosDePrecarga(
    [{ nombre: "Pipe", colegio: "Colegio CACS", grado: "Quinto", motivo: "sin_lista" }],
    MAX_HIJOS,
  );
  assert.equal(avisos.length, 1);
  assert.doesNotMatch(avisos[0]!, /Agregar otro hijo/);
  assert.match(avisos[0]!, /otro pedido/);
});
