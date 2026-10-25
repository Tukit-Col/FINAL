// Pruebas del 429 del limite de tasa (ADR 0047) del lado del servidor: un 429
// nunca se lee como "sin sesion" ni como "sin datos". Runner nativo de Node
// (type-stripping), sin dependencias: `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { avisoDeLimite, esLimiteDeTasa, fallaCerradoSalvoLimite } from "../src/lib/limite.ts";

// La misma forma que `ErrorTukit` y `FalloApi`: estado, mensaje y detalle.
class Fallo extends Error {
  estado: number;
  detalle: Record<string, unknown>;
  constructor(estado: number, mensaje: string, detalle: Record<string, unknown> = {}) {
    super(mensaje);
    this.estado = estado;
    this.detalle = detalle;
  }
}

const MENSAJE = "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 30 segundos.";
const limite = new Fallo(429, MENSAJE, { reintentar_en_segundos: 30 });

test("un token rechazado sigue siendo 'sin sesion'", async () => {
  const sesion = await fallaCerradoSalvoLimite(async () => {
    throw new Fallo(401, "token invalido");
  }, null);
  assert.equal(sesion, null);
});

test("un 429 no se traga como 'sin sesion': se propaga", async () => {
  await assert.rejects(
    fallaCerradoSalvoLimite(async () => {
      throw limite;
    }, null),
    (causa) => causa === limite,
  );
});

test("un 429 tampoco se vuelve una lista vacia", async () => {
  await assert.rejects(
    fallaCerradoSalvoLimite<string[]>(async () => {
      throw limite;
    }, []),
    (causa) => causa === limite,
  );
});

test("lo que sale bien pasa tal cual", async () => {
  assert.deepEqual(await fallaCerradoSalvoLimite(async () => ["a"], []), ["a"]);
});

test("el aviso trae el mensaje del gateway y la espera", () => {
  assert.deepEqual(avisoDeLimite(limite), { mensaje: MENSAJE, segundos: 30 });
  assert.equal(esLimiteDeTasa(limite), true);
});

test("otro fallo no es un aviso de limite", () => {
  assert.equal(avisoDeLimite(new Fallo(503, "caido")), null);
  assert.equal(avisoDeLimite(new Error("x")), null);
  assert.equal(avisoDeLimite(null), null);
});
