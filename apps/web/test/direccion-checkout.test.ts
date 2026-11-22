import { test } from "node:test";
import assert from "node:assert/strict";
import { aplicarLugarElegido, entregaDeCheckout, escribirDireccionAMano } from "../src/lib/direccion-checkout.ts";

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

const ENTREGA = {
  destinatario: "Ana",
  direccion: "Calle 72 # 10-34",
  indicaciones: "  Torre 2  ",
  localidad: "Chapinero",
  departamento: "  Cundinamarca ",
  latitud: 4.65 as number | null,
  longitud: -74.05 as number | null,
  ciudad: "Bogotá",
};

test("elegir un lugar toma dirección, pin y localidad, y conserva el departamento si el lugar no lo trae", () => {
  const lugar = { direccion: "Carrera 7 # 1-1", latitud: 4.6, longitud: -74.0, localidad: "Santa Fe" };
  assert.deepEqual(aplicarLugarElegido(ENTREGA, lugar), {
    ...ENTREGA,
    direccion: "Carrera 7 # 1-1",
    latitud: 4.6,
    longitud: -74.0,
    localidad: "Santa Fe",
  });
  const sinPin = aplicarLugarElegido(ENTREGA, { direccion: "x", localidad: "Suba", departamento: "Otro" });
  assert.equal(sinPin.latitud, null);
  assert.equal(sinPin.longitud, null);
  assert.equal(sinPin.departamento, "Otro");
});

test("la entrega del checkout recorta los opcionales y omite los vacíos", () => {
  assert.deepEqual(entregaDeCheckout(ENTREGA), {
    destinatario: "Ana",
    direccion: "Calle 72 # 10-34",
    ciudad: "Bogotá",
    indicaciones: "Torre 2",
    localidad: "Chapinero",
    departamento: "Cundinamarca",
    latitud: 4.65,
    longitud: -74.05,
  });
  assert.deepEqual(
    entregaDeCheckout({ ...ENTREGA, indicaciones: " ", localidad: "", departamento: "", latitud: null, longitud: null }),
    { destinatario: "Ana", direccion: "Calle 72 # 10-34", ciudad: "Bogotá" },
  );
});

test("el pin solo viaja si están las dos coordenadas", () => {
  const sinLongitud = entregaDeCheckout({ ...ENTREGA, longitud: null });
  assert.equal("latitud" in sinLongitud, false);
  assert.equal("longitud" in sinLongitud, false);
});
