// Pruebas de la tenencia simulada del acudiente (usuarios.ts).
//
// Mismo runner nativo que el resto del paquete (`node --test` sobre TS por
// type-stripping), sin agregar dependencias. Se prueba `usuarios.ts` y no la
// clase `OrigenSimulado` entera a proposito: esa arrastra imports de VALOR sin
// extension (semillas, catalogo) que el type-stripping de Node no resuelve,
// igual que el resto de la suite se limita a los helpers de solo-tipo. Aqui
// vive toda la logica nueva del origen simulado (siembra, almacen y token), asi
// que probarla cubre lo que el camino de dos vias de `/empezar` necesita.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  leerTokenSimulado,
  matriculasDeCorreo,
  registrarMatriculasSimuladas,
  tokenSimulado,
} from "../src/simulado/usuarios.ts";

test("mama trae su hijo sembrado, para precargar /empezar", () => {
  const matriculas = matriculasDeCorreo("mama@ejemplo.com");
  assert.equal(matriculas.length, 1);
  assert.equal(matriculas[0].colegio_id, "2.13");
  assert.equal(matriculas[0].grado, "Quinto");
  // Nada del menor: la matricula es ambito de tenencia, no identidad.
  assert.ok(!("apodo" in matriculas[0]));
});

test("un correo sin tenencia devuelve lista vacia", () => {
  assert.deepEqual(matriculasDeCorreo("desconocido@ejemplo.com"), []);
});

test("registrar guarda las matriculas del alta nueva", () => {
  registrarMatriculasSimuladas("nueva@ejemplo.com", [
    { colegio_id: "1.1", grado: "Primero" },
  ]);
  const matriculas = matriculasDeCorreo("nueva@ejemplo.com");
  assert.equal(matriculas.length, 1);
  assert.equal(matriculas[0].colegio_id, "1.1");
  assert.equal(matriculas[0].grado, "Primero");
});

test("el token simulado hace ida y vuelta al correo", () => {
  assert.equal(leerTokenSimulado(tokenSimulado("x@y.com")), "x@y.com");
  assert.equal(leerTokenSimulado("basura"), null);
});
