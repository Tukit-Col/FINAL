import { test } from "node:test";
import assert from "node:assert/strict";
import { chipDeSolicitud, fechaLegible, rangoDeChip } from "../src/lib/panel-cuenta.ts";

const s = (tipo: string, estado?: string) => ({ tipo, estado }) as never;

test("una compra manda sobre el estado de la solicitud", () => {
  assert.deepEqual(chipDeSolicitud(s("trabajo", "procesando"), { estado: "comprado" }), { texto: "Comprado", tono: "exito" });
  assert.deepEqual(chipDeSolicitud(s("trabajo", "publicado"), { estado: "pendiente_pago" }), { texto: "Pago pendiente", tono: "aviso" });
});

test("sin compra, el chip sale del tipo y del estado", () => {
  assert.equal(chipDeSolicitud(s("recibida"), null).texto, "En revisión");
  assert.equal(chipDeSolicitud(s("aprobada"), null).texto, "Listo");
  assert.equal(chipDeSolicitud(s("trabajo", "publicado"), null).texto, "Listo");
  assert.equal(chipDeSolicitud(s("trabajo", "encolado"), null).texto, "Armando");
  assert.equal(chipDeSolicitud(s("trabajo", "procesando"), null).tono, "info");
  assert.equal(chipDeSolicitud(s("trabajo", "cancelado"), null).texto, "Cancelada");
  assert.equal(chipDeSolicitud(s("trabajo", "espera_revision"), null).texto, "En revisión");
});

test("el chip más avanzado gana y uno desconocido vale cero", () => {
  assert.ok(rangoDeChip({ texto: "Listo", tono: "exito" }) > rangoDeChip({ texto: "Armando", tono: "info" }));
  assert.ok(rangoDeChip({ texto: "Armando", tono: "info" }) > rangoDeChip({ texto: "En revisión", tono: "aviso" }));
  assert.equal(rangoDeChip({ texto: "Cancelada", tono: "neutro" }), 0);
});

test("la fecha se escribe en español con mes corto o largo", () => {
  const corta = fechaLegible("2026-03-05T12:00:00Z");
  const larga = fechaLegible("2026-03-05T12:00:00Z", "long");
  assert.match(corta, /mar/i);
  assert.match(larga, /marzo/i);
});
