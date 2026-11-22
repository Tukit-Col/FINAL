import { test } from "node:test";
import assert from "node:assert/strict";
import { designarColegio } from "../src/lib/designar-colegio.ts";

const CACS = { colegio_id: "17127bcf", dane: "311001093652" };
const SIN_DANE = { colegio_id: "libre", dane: null };
const COLEGIOS = [SIN_DANE, CACS];

test("un colegio_id manda sobre lo demás", () => {
  assert.deepEqual(
    designarColegio({ colegio_id: " cacs ", colegio_dane: "311001105731", colegio_nombre: "X" }, COLEGIOS),
    { colegio_id: "cacs" },
  );
});

test("un DANE que ya es de un colegio de Tukit se reconduce a ese colegio", () => {
  assert.deepEqual(
    designarColegio({ colegio_dane: "311001093652", colegio_nombre: "COLEGIO AGUSTINIANO CIUDAD SALITRE" }, COLEGIOS),
    { colegio_id: "17127bcf" },
  );
});

test("un DANE nuevo viaja con su nombre", () => {
  assert.deepEqual(
    designarColegio({ colegio_dane: "311001105731", colegio_nombre: " ACADEMIA CENTRAL " }, COLEGIOS),
    { colegio_dane: "311001105731", colegio_nombre: "ACADEMIA CENTRAL" },
  );
});

test("un DANE nuevo sin nombre no alcanza", () => {
  assert.equal(designarColegio({ colegio_dane: "311001105731" }, COLEGIOS), null);
});

test("un nombre escrito a mano viaja solo", () => {
  assert.deepEqual(designarColegio({ colegio_nombre: "Gimnasio del Bosque" }, COLEGIOS), {
    colegio_nombre: "Gimnasio del Bosque",
  });
});

test("sin colegio, o con campos que no son texto, no hay designación", () => {
  assert.equal(designarColegio({}, COLEGIOS), null);
  assert.equal(designarColegio({ colegio_id: "  ", colegio_nombre: "" }, COLEGIOS), null);
  assert.equal(designarColegio({ colegio_id: 42, colegio_nombre: null }, COLEGIOS), null);
});
