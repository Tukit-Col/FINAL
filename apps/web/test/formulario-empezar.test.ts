import { test } from "node:test";
import assert from "node:assert/strict";
import {
  contactoCompleto,
  estadoDePaso,
  faltantesDeContacto,
  faltantesDeHijos,
  faltantesEnOrden,
  gradoVerificado,
  hijoCompleto,
  hijoVacio,
  necesitaArchivo,
  pasoActual,
  pasoEsFuturo,
  perfilDeSeleccion,
  prioridadElegida,
  siguienteReferencia,
  unirEnLista,
  type HijoFormulario,
} from "../src/lib/formulario-empezar.ts";

const COLEGIOS = new Map([["san-pedro", { grados: ["Primero", "Tercero"] }]]);
const ARCHIVO = {} as File;

function hijo(cambio: Partial<HijoFormulario> = {}): HijoFormulario {
  return { ...hijoVacio(1), ...cambio };
}

test("un grado con lista verificada no pide archivo y queda completo", () => {
  const h = hijo({ colegioId: "san-pedro", grado: "Primero" });
  assert.equal(gradoVerificado(h, COLEGIOS), true);
  assert.equal(necesitaArchivo(h, COLEGIOS), false);
  assert.equal(hijoCompleto(h, COLEGIOS), true);
});

test("un grado sin lista verificada pide archivo hasta que se adjunta", () => {
  const sinArchivo = hijo({ colegioId: "san-pedro", grado: "Quinto" });
  assert.equal(necesitaArchivo(sinArchivo, COLEGIOS), true);
  assert.equal(hijoCompleto(sinArchivo, COLEGIOS), false);
  assert.equal(hijoCompleto({ ...sinArchivo, archivo: ARCHIVO }, COLEGIOS), true);
});

test("un colegio escrito a mano exige nombre, grado y archivo", () => {
  const h = hijo({ colegioNombre: "Colegio Nuevo", grado: "Tercero" });
  assert.equal(necesitaArchivo(h, COLEGIOS), true);
  assert.equal(hijoCompleto(h, COLEGIOS), false);
  assert.equal(hijoCompleto({ ...h, archivo: ARCHIVO }, COLEGIOS), true);
  assert.equal(hijoCompleto(hijo({ colegioNombre: "Colegio Nuevo", archivo: ARCHIVO }), COLEGIOS), false);
});

test("los faltantes de los hijos nombran al hijo solo si hay más de uno", () => {
  assert.deepEqual(faltantesDeHijos([hijo()], COLEGIOS), ["el colegio"]);
  assert.deepEqual(faltantesDeHijos([hijo({ colegioId: "san-pedro" })], COLEGIOS), ["el grado"]);
  assert.deepEqual(
    faltantesDeHijos([hijo({ colegioId: "san-pedro", grado: "Quinto" })], COLEGIOS),
    ["la lista"],
  );
  const dos = [hijo({ colegioId: "san-pedro", grado: "Primero" }), hijo({ referencia: "hijo-2" })];
  assert.deepEqual(faltantesDeHijos(dos, COLEGIOS), ["el colegio del hijo 2"]);
});

test("los faltantes de contacto salen en el orden del formulario", () => {
  const vacio = { correo: "", celular: "", claveOk: false, aceptaTerminos: false };
  assert.deepEqual(faltantesDeContacto(vacio), [
    "tu correo",
    "una contraseña de al menos 8 caracteres",
    "aceptar la política de datos y los términos",
    "tu celular",
  ]);
  const completo = { correo: "a@b.co", celular: "3001234", claveOk: true, aceptaTerminos: true };
  assert.deepEqual(faltantesDeContacto(completo), []);
  assert.equal(contactoCompleto(completo), true);
  assert.equal(contactoCompleto({ ...completo, celular: "123456" }), false);
});

test("el paso actual sigue el modo y lo que falta", () => {
  const sin = { contacto: [], hijos: [] };
  assert.equal(pasoActual("elegir", sin), null);
  assert.equal(pasoActual("existente", sin), null);
  assert.equal(pasoActual("nuevo", { contacto: ["tu correo"], hijos: ["el colegio"] }), "registro");
  assert.equal(pasoActual("nuevo", { contacto: [], hijos: ["el colegio"] }), "hijos");
  assert.equal(pasoActual("autenticado", { contacto: ["tu correo"], hijos: [] }), "preferencias");
});

test("el estado de cada paso: completo si ya se pasó y no falta nada, futuro si falta", () => {
  const faltantes = { contacto: [], hijos: ["el grado"] };
  assert.equal(estadoDePaso("hijos", "hijos", faltantes), "actual");
  assert.equal(estadoDePaso("preferencias", "hijos", faltantes), "futuro");
  assert.equal(estadoDePaso("registro", "hijos", { contacto: [], hijos: [] }), "completo");
  assert.equal(estadoDePaso("hijos", "preferencias", { contacto: [], hijos: [] }), "completo");
  assert.equal(estadoDePaso("hijos", "preferencias", { contacto: [], hijos: ["el grado"] }), "futuro");
  assert.equal(estadoDePaso("registro", null, faltantes), "futuro");
  assert.equal(pasoEsFuturo("preferencias", "hijos"), true);
  assert.equal(pasoEsFuturo("hijos", "hijos"), false);
  assert.equal(pasoEsFuturo("hijos", null), false);
});

test("los faltantes se ordenan según el modo", () => {
  const f = { contacto: ["tu correo"], hijos: ["el colegio"] };
  assert.deepEqual(faltantesEnOrden("nuevo", f), ["tu correo", "el colegio"]);
  assert.deepEqual(faltantesEnOrden("autenticado", f), ["el colegio", "tu correo"]);
});

test("el perfil marcado: Fan si pidió personaje; si no, Premium solo con calidad", () => {
  assert.equal(perfilDeSeleccion("precio", true), "Fan");
  assert.equal(perfilDeSeleccion("calidad", false), "Premium");
  assert.equal(perfilDeSeleccion("equilibrio", false), "Ahorrador");
  assert.equal(perfilDeSeleccion("precio", false), "Ahorrador");
});

test("cada prioridad conserva sus pesos y una clave desconocida cae al punto medio", () => {
  assert.equal(prioridadElegida("precio").pesos.precio, 0.6);
  assert.equal(prioridadElegida("calidad").disposicion_sobreprecio, 0.1);
  assert.equal(prioridadElegida("equilibrio").clave, "equilibrio");
  assert.equal(prioridadElegida("otra" as never).clave, "equilibrio");
});

test("la lista se une con comas y una y final", () => {
  assert.equal(unirEnLista([]), "");
  assert.equal(unirEnLista(["a"]), "a");
  assert.equal(unirEnLista(["a", "b"]), "a y b");
  assert.equal(unirEnLista(["a", "b", "c"]), "a, b y c");
});

test("la referencia del hijo nuevo sigue a la mayor existente", () => {
  assert.equal(siguienteReferencia([]), 1);
  assert.equal(siguienteReferencia([hijoVacio(1), hijoVacio(3)]), 4);
});
