// Localidades de Bogota desde los componentes de Google Places (New) y el
// enlace a Google Maps del envio. Puro, con `node --test`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  direccionDesdeComponentes,
  enlaceGoogleMaps,
  esBogota,
  LOCALIDADES_BOGOTA,
  localidadCanonica,
  type ComponenteDireccion,
} from "../src/localidades.ts";

function c(longText: string, ...types: string[]): ComponenteDireccion {
  return { longText, shortText: longText, types };
}

const BOGOTA = [
  c("Bogotá", "locality", "political"),
  c("Bogotá, D.C.", "administrative_area_level_1", "political"),
  c("Colombia", "country", "political"),
];

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

test("Bogota con sublocality: ciudad, localidad y departamento", () => {
  const r = direccionDesdeComponentes([
    c("Calle 72 #10-34", "street_address"),
    c("Chapinero", "sublocality_level_1", "sublocality", "political"),
    ...BOGOTA,
  ]);
  assert.deepEqual(r, { ciudad: "Bogotá", localidad: "Chapinero", departamento: "Bogotá, D.C." });
});

test("Bogota con 'Localidad de' en otro nivel", () => {
  const r = direccionDesdeComponentes([
    c("Quinta Camacho", "neighborhood", "political"),
    c("Localidad de Chapinero", "administrative_area_level_3", "political"),
    ...BOGOTA,
  ]);
  assert.equal(r.localidad, "Chapinero");
});

test("la localidad gana sobre un barrio que no es localidad", () => {
  const r = direccionDesdeComponentes([
    c("Las Aguas", "neighborhood", "political"),
    c("Santafé", "sublocality_level_1", "political"),
    ...BOGOTA,
  ]);
  assert.equal(r.localidad, "Santa Fe");
});

test("Bogota sin sublocality: la localidad queda vacia para elegirla", () => {
  const r = direccionDesdeComponentes([c("Quinta Camacho", "neighborhood", "political"), ...BOGOTA]);
  assert.deepEqual(r, { ciudad: "Bogotá", localidad: "", departamento: "Bogotá, D.C." });
});

test("un barrio que se llama como una localidad no es esa localidad", () => {
  // El barrio Santa Fe queda en Los Mártires, no en la localidad Santa Fe:
  // sin sublocality, la localidad queda vacia para que el acudiente la elija.
  const r = direccionDesdeComponentes([
    c("Calle 22 #17-30", "street_address"),
    c("Santa Fe", "neighborhood", "political"),
    ...BOGOTA,
  ]);
  assert.deepEqual(r, { ciudad: "Bogotá", localidad: "", departamento: "Bogotá, D.C." });
});

test("Bogota solo como departamento sigue siendo Bogota", () => {
  const r = direccionDesdeComponentes([
    c("Suba", "sublocality_level_1", "political"),
    c("Bogotá, D.C.", "administrative_area_level_1", "political"),
  ]);
  assert.deepEqual(r, { ciudad: "Bogotá, D.C.", localidad: "Suba", departamento: "Bogotá, D.C." });
});

test("Soacha y Chia no tienen localidad aunque un barrio se llame como una", () => {
  const soacha = direccionDesdeComponentes([
    c("Bosa", "neighborhood", "political"),
    c("Soacha", "locality", "political"),
    c("Cundinamarca", "administrative_area_level_1", "political"),
  ]);
  assert.deepEqual(soacha, { ciudad: "Soacha", localidad: "", departamento: "Cundinamarca" });
  const chia = direccionDesdeComponentes([
    c("Chía", "locality", "political"),
    c("Sabana Centro", "administrative_area_level_2", "political"),
    c("Cundinamarca", "administrative_area_level_1", "political"),
  ]);
  assert.deepEqual(chia, { ciudad: "Chía", localidad: "", departamento: "Cundinamarca" });
});

test("sin componentes, o con textos vacios, todo queda vacio", () => {
  const vacio = { ciudad: "", localidad: "", departamento: "" };
  assert.deepEqual(direccionDesdeComponentes([]), vacio);
  assert.deepEqual(direccionDesdeComponentes(null), vacio);
  assert.deepEqual(
    direccionDesdeComponentes([{ longText: null, shortText: null, types: ["locality"] }]),
    vacio,
  );
  // Sin `locality`, el municipio sale del nivel 2.
  assert.equal(
    direccionDesdeComponentes([c("Zipaquirá", "administrative_area_level_2", "political")]).ciudad,
    "Zipaquirá",
  );
});

test("esBogota reconoce sus formas", () => {
  for (const ciudad of ["Bogotá", "bogota", "Bogotá, D.C.", "BOGOTA D.C.", "Santafé de Bogotá"]) {
    assert.equal(esBogota(ciudad), true, ciudad);
  }
  for (const ciudad of ["Soacha", "", null, "Bogotá Norte"]) assert.equal(esBogota(ciudad), false);
});

test("enlace a Maps: con place_id fija el lugar, sin el busca por texto", () => {
  assert.equal(
    enlaceGoogleMaps({ direccion: "Calle 72 #10-34, Bogotá", ciudad: "Bogotá", google_place_id: "ChIJ abc" }),
    "https://www.google.com/maps/search/?api=1&query=Calle%2072%20%2310-34%2C%20Bogot%C3%A1&query_place_id=ChIJ%20abc",
  );
  // Escrita a mano sin la ciudad: se le agrega para que Maps no busque en otro pais.
  assert.equal(
    enlaceGoogleMaps({ direccion: "Cra 7 # 45-10", ciudad: "Bogotá", google_place_id: null }),
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
  // Una sola coordenada no sirve: cae a la búsqueda por texto.
  assert.match(enlaceGoogleMaps({ direccion: "Calle 72 #10-34", latitud: 4.65 }), /query=Calle%2072/);
});
