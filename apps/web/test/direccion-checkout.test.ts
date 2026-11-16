// La regla pura del campo de dirección del checkout: qué se borra al editar a
// mano una dirección ya elegida.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/direccion-checkout.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { escribirDireccionAMano } from "../src/lib/direccion-checkout.ts";

const CON_LUGAR = {
  direccion: "Cl. 26 #69-76, Bogotá, Colombia",
  google_place_id: "ChIJ-lugar",
  localidad: "Fontibón",
  ciudad: "Bogotá",
};

test("editar a mano una dirección con lugar elegido suelta el lugar y la localidad", () => {
  assert.deepEqual(escribirDireccionAMano(CON_LUGAR, "Cl. 26 #69-7"), {
    direccion: "Cl. 26 #69-7",
    google_place_id: "",
    localidad: "",
    ciudad: "Bogotá",
  });
});

test("editar una dirección escrita a mano conserva la localidad elegida", () => {
  const manual = { ...CON_LUGAR, google_place_id: "" };
  assert.deepEqual(escribirDireccionAMano(manual, "Calle 26 # 69-76"), {
    ...manual,
    direccion: "Calle 26 # 69-76",
  });
});

test("editar a mano una dirección con pin de OpenStreetMap suelta el pin y la localidad", () => {
  const conPin = {
    direccion: "Calle 72 # 10-34",
    google_place_id: "",
    localidad: "Chapinero",
    latitud: 4.65,
    longitud: -74.05,
  };
  assert.deepEqual(escribirDireccionAMano(conPin, "Calle 73 # 10-34"), {
    direccion: "Calle 73 # 10-34",
    google_place_id: "",
    localidad: "",
    latitud: null,
    longitud: null,
  });
});

test("sin pin ni lugar elegido, escribir solo cambia el texto", () => {
  const manual = { direccion: "Cl", google_place_id: "", localidad: "Suba", latitud: null, longitud: null };
  assert.deepEqual(escribirDireccionAMano(manual, "Cll 1"), { ...manual, direccion: "Cll 1" });
});
