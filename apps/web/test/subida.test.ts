// La subida de listas desde la web: los topes que se cortan antes de leer el
// cuerpo y la ruta de "Recibimos tu lista" que sigue a la subida.
// Runner nativo de Node (type-stripping): `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MAX_BYTES_ARCHIVO,
  MAX_BYTES_PETICION,
  cuerpoDemasiadoGrande,
  motivoDeRechazo,
} from "../src/lib/subida.ts";
import { cuantasDiferidas, esDiferida, rutaRecibimos } from "../src/lib/recibimos.ts";

const conLargo = (largo?: number) =>
  new Request("http://tukit.test/api/listas/subir", {
    method: "POST",
    headers: largo === undefined ? {} : { "content-length": String(largo) },
  });

test("un cuerpo declarado sobre el tope se corta; sin cabecera no se adivina", () => {
  assert.equal(cuerpoDemasiadoGrande(conLargo(MAX_BYTES_PETICION + 1)), true);
  assert.equal(cuerpoDemasiadoGrande(conLargo(MAX_BYTES_PETICION)), false);
  assert.equal(cuerpoDemasiadoGrande(conLargo()), false);
});

test("el archivo pasa con el tamano y los tipos que promete la pantalla", () => {
  assert.equal(motivoDeRechazo({ size: MAX_BYTES_ARCHIVO, type: "application/pdf" }), null);
  assert.equal(motivoDeRechazo({ size: 1, type: "image/webp" }), null);
  assert.equal(motivoDeRechazo({ size: 1, type: "" }), null);
  assert.match(motivoDeRechazo({ size: MAX_BYTES_ARCHIVO + 1, type: "image/jpeg" }) ?? "", /10 MB/);
  assert.match(motivoDeRechazo({ size: 1, type: "application/zip" }) ?? "", /PDF, JPG/);
});

// --- Recibimos tu lista: subidas y diferidas (ADR 0040) ------------------------

const importada = { version_id: "v-1" } as const;
const diferida = { version_id: null, estado: "pendiente" } as const;

test("con el catalogo arriba la ruta es la de siempre", () => {
  assert.equal(rutaRecibimos([importada, importada]), "/recibimos?pendientes=2");
  assert.equal(rutaRecibimos([importada], "t-1"), "/recibimos?pendientes=1&trabajo=t-1");
});

test("las listas que quedaron pendientes viajan aparte como diferidas", () => {
  assert.equal(rutaRecibimos([importada, diferida]), "/recibimos?pendientes=2&diferidas=1");
  assert.equal(
    rutaRecibimos([diferida, diferida], "t-1"),
    "/recibimos?pendientes=2&diferidas=2&trabajo=t-1",
  );
});

test("una subida sin version cuenta como diferida aunque no traiga estado", () => {
  assert.equal(esDiferida({ version_id: null }), true);
  assert.equal(esDiferida(importada), false);
});

test("el numero de diferidas de la URL se acota a las listas subidas", () => {
  assert.equal(cuantasDiferidas(undefined, 2), 0);
  assert.equal(cuantasDiferidas("abc", 2), 0);
  assert.equal(cuantasDiferidas("0", 2), 0);
  assert.equal(cuantasDiferidas("1", 2), 1);
  assert.equal(cuantasDiferidas("9", 2), 2);
});
