import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buscarColegios,
  imagenesPorDane,
  inicialesColegio,
  logoDeColegio,
  logoDelDirectorio,
  normalizarBusqueda,
  prepararBusqueda,
  type EntradaDirectorio,
} from "../src/colegios-busqueda.ts";

const SALITRE: EntradaDirectorio = {
  dane: "311001093652",
  nombre: "COLEGIO AGUSTINIANO CIUDAD SALITRE",
  localidad: "FONTIBON",
  imageURL: "https://agustinianosalitre.edu.co/escudo.png",
};
const NORTE: EntradaDirectorio = {
  dane: "311769000751",
  nombre: "COLEGIO AGUSTINIANO NORTE",
  localidad: "SUBA",
  imageURL: null,
};
const SAN_JOSE: EntradaDirectorio = {
  dane: "111001000001",
  nombre: "COLEGIO SAN JOSÉ",
  localidad: "CHAPINERO",
  imageURL: null,
};
const DIRECTORIO = [SALITRE, NORTE, SAN_JOSE];

const CACS = { colegio_id: "cacs", nombre: "Colegio CACS", dane: "311001093652", logo_url: null };
const SIN_DANE = { colegio_id: "libre", nombre: "Gimnasio Agustiniano Libre", dane: null, logo_url: null };

test("normalizar pliega mayusculas y acentos", () => {
  assert.equal(normalizarBusqueda("JOSÉ Ñandú Bogotá"), "jose nandu bogota");
});

test("con menos de tres letras no hay resultados", () => {
  const prep = prepararBusqueda([CACS], DIRECTORIO);
  assert.deepEqual(buscarColegios(prep, "ag"), { colegios: [], directorio: [] });
  assert.deepEqual(buscarColegios(prep, "   ag  "), { colegios: [], directorio: [] });
});

test("la entrada del directorio con el DANE de un colegio de Tukit se reconduce a ese colegio", () => {
  const prep = prepararBusqueda([CACS], DIRECTORIO);
  const r = buscarColegios(prep, "salitre");
  assert.deepEqual(r.colegios, [
    { colegio: CACS, etiqueta: "COLEGIO AGUSTINIANO CIUDAD SALITRE · Colegio CACS" },
  ]);
  assert.deepEqual(r.directorio, []);
});

test("el colegio reconducido tambien casa por su nombre en Tukit", () => {
  const prep = prepararBusqueda([CACS], DIRECTORIO);
  assert.equal(buscarColegios(prep, "cacs").colegios[0]?.colegio.colegio_id, "cacs");
});

test("mezcla: primero los colegios de Tukit, luego el directorio, sin acentos de por medio", () => {
  const prep = prepararBusqueda([CACS, SIN_DANE], DIRECTORIO);
  const r = buscarColegios(prep, "agustiniano");
  assert.deepEqual(
    r.colegios.map((c) => c.etiqueta),
    ["COLEGIO AGUSTINIANO CIUDAD SALITRE · Colegio CACS", "Gimnasio Agustiniano Libre"],
  );
  assert.deepEqual(r.directorio, [NORTE]);
  assert.deepEqual(buscarColegios(prep, "jose").directorio, [SAN_JOSE]);
});

test("el directorio se corta en 30 y el tope se puede cambiar", () => {
  const muchos: EntradaDirectorio[] = Array.from({ length: 45 }, (_, i) => ({
    dane: String(100000000000 + i),
    nombre: `COLEGIO DISTRITAL ${i}`,
    localidad: "BOSA",
    imageURL: null,
  }));
  const prep = prepararBusqueda([], muchos);
  assert.equal(buscarColegios(prep, "distrital").directorio.length, 30);
  assert.equal(buscarColegios(prep, "distrital", 5).directorio.length, 5);
});

test("dos colegios con el mismo DANE: gana el primero", () => {
  const otro = { ...CACS, colegio_id: "cacs-2", nombre: "Otro CACS" };
  const prep = prepararBusqueda([CACS, otro], DIRECTORIO);
  assert.deepEqual(
    buscarColegios(prep, "salitre").colegios.map((c) => c.colegio.colegio_id),
    ["cacs"],
  );
});

test("iniciales: dos palabras significativas, en mayuscula", () => {
  assert.equal(inicialesColegio("COLEGIO AGUSTINIANO DE SAN NICOLAS"), "CA");
  assert.equal(inicialesColegio("Gimnasio del Norte"), "GN");
  assert.equal(inicialesColegio("La Sa"), "LS");
  assert.equal(inicialesColegio(""), "");
});

test("logo: manda el de Identidad, luego el del directorio por DANE, si no ninguno", () => {
  const imagenes = imagenesPorDane(DIRECTORIO);
  assert.equal(imagenes.size, 1);
  assert.equal(
    logoDeColegio({ logo_url: "https://tukit.co/cacs.png", dane: SALITRE.dane }, imagenes),
    "https://tukit.co/cacs.png",
  );
  assert.equal(logoDeColegio({ logo_url: null, dane: SALITRE.dane }, imagenes), SALITRE.imageURL);
  assert.equal(logoDeColegio({ logo_url: "  ", dane: SALITRE.dane }, imagenes), SALITRE.imageURL);
  assert.equal(logoDeColegio({ logo_url: null, dane: NORTE.dane }, imagenes), null);
  assert.equal(logoDeColegio({ logo_url: null, dane: null }, imagenes), null);
});

test("logo del directorio: solo cuando el colegio no tiene uno propio", () => {
  const imagenes = imagenesPorDane(DIRECTORIO);
  assert.equal(logoDelDirectorio({ logo_url: null, dane: SALITRE.dane }, imagenes), SALITRE.imageURL);
  assert.equal(logoDelDirectorio({ logo_url: " ", dane: SALITRE.dane }, imagenes), SALITRE.imageURL);
  assert.equal(logoDelDirectorio({ logo_url: "https://tukit.co/cacs.png", dane: SALITRE.dane }, imagenes), null);
  assert.equal(logoDelDirectorio({ logo_url: null, dane: NORTE.dane }, imagenes), null);
  assert.equal(logoDelDirectorio({ logo_url: null, dane: null }, imagenes), null);
});
