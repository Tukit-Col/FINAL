import { test } from "node:test";
import assert from "node:assert/strict";
import { escribirDireccionAMano } from "../src/lib/direccion-checkout.ts";

test("editar a mano una dirección con pin de OpenStreetMap suelta el pin y la localidad", () => {
  const conPin = {
    direccion: "Calle 72 # 10-34",
    localidad: "Chapinero",
    ciudad: "Bogotá",
    latitud: 4.65,
    longitud: -74.05,
  };
  assert.deepEqual(escribirDireccionAMano(conPin, "Calle 73 # 10-34"), {
    direccion: "Calle 73 # 10-34",
    localidad: "",
    ciudad: "Bogotá",
    latitud: null,
    longitud: null,
  });
});

test("sin pin, escribir solo cambia el texto y conserva la localidad elegida", () => {
  const manual = { direccion: "Cl", localidad: "Suba", latitud: null, longitud: null };
  assert.deepEqual(escribirDireccionAMano(manual, "Cll 1"), { ...manual, direccion: "Cll 1" });
});

test("un formulario sin campos de coordenadas no los recibe al soltar el pin", () => {
  const sinCampos = { direccion: "Cl", localidad: "Suba" };
  assert.deepEqual(escribirDireccionAMano(sinCampos, "Cll 1"), { direccion: "Cll 1", localidad: "Suba" });
});
