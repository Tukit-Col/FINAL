import { test } from "node:test";
import assert from "node:assert/strict";
import {
  enlaceGoogleMaps,
  esBogota,
  LOCALIDADES_BOGOTA,
  localidadCanonica,
} from "../src/localidades.ts";

test("son las 20 localidades, sin repetir", () => {
  assert.equal(LOCALIDADES_BOGOTA.length, 20);
  assert.equal(new Set(LOCALIDADES_BOGOTA).size, 20);
  for (const l of LOCALIDADES_BOGOTA) assert.equal(localidadCanonica(l), l);
});

test("la comparacion ignora acentos, mayusculas, espacios y 'Localidad de'", () => {
  assert.equal(localidadCanonica("Localidad de Chapinero"), "Chapinero");
  assert.equal(localidadCanonica("  USAQUEN "), "Usaquén");
  assert.equal(localidadCanonica("Santafé"), "Santa Fe");
  assert.equal(localidadCanonica("Mártires"), "Los Mártires");
  assert.equal(localidadCanonica("Candelaria"), "La Candelaria");
  assert.equal(localidadCanonica("Rafael Uribe"), "Rafael Uribe Uribe");
  assert.equal(localidadCanonica("engativa"), "Engativá");
  assert.equal(localidadCanonica("Chapinero Alto"), null);
  assert.equal(localidadCanonica(""), null);
  assert.equal(localidadCanonica(null), null);
});

test("enlace a Maps: busca por el texto de la direccion", () => {
  assert.equal(
    enlaceGoogleMaps({ direccion: "Cra 7 # 45-10", ciudad: "Bogotá" }),
    "https://www.google.com/maps/search/?api=1&query=Cra%207%20%23%2045-10%2C%20Bogot%C3%A1",
  );
  assert.equal(
    enlaceGoogleMaps({ direccion: "Cra 7 # 45-10" }),
    "https://www.google.com/maps/search/?api=1&query=Cra%207%20%23%2045-10",
  );
});

test("con el pin confirmado en OpenStreetMap el enlace abre ese punto exacto", () => {
  assert.equal(
    enlaceGoogleMaps({ direccion: "Calle 72 #10-34", ciudad: "Bogotá", latitud: 4.6518, longitud: -74.051 }),
    "https://www.google.com/maps/search/?api=1&query=4.6518,-74.051",
  );
  assert.match(enlaceGoogleMaps({ direccion: "Calle 72 #10-34", latitud: 4.65 }), /query=Calle%2072/);
});
