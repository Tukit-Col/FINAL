// Los topes de subida que se cortan en la web antes de leer el cuerpo.
// Runner nativo de Node (type-stripping): `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MAX_BYTES_ARCHIVO,
  MAX_BYTES_PETICION,
  cuerpoDemasiadoGrande,
  motivoDeRechazo,
} from "../src/lib/subida.ts";

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
