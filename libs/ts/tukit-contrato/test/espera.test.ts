import { test } from "node:test";
import assert from "node:assert/strict";
import { conEspera, esperaDe429, mensajeDeEspera, segundosDeEspera } from "../src/espera.ts";

test("retry-after en segundos", () => {
  assert.equal(segundosDeEspera("42"), 42);
  assert.equal(segundosDeEspera(" 7 "), 7);
  assert.equal(segundosDeEspera("0"), 1);
});

test("retry-after como fecha http", () => {
  const ahora = Date.parse("Wed, 21 Oct 2026 07:28:00 GMT");
  assert.equal(segundosDeEspera("Wed, 21 Oct 2026 07:29:30 GMT", ahora), 90);
  assert.equal(segundosDeEspera("Wed, 21 Oct 2026 07:00:00 GMT", ahora), 1);
});

test("retry-after ausente o ilegible", () => {
  assert.equal(segundosDeEspera(null), null);
  assert.equal(segundosDeEspera(""), null);
  assert.equal(segundosDeEspera("pronto"), null);
  assert.equal(segundosDeEspera("-5"), null);
  assert.equal(segundosDeEspera("2026-10-21"), null);
});

test("la espera del cuerpo gana a la de la cabecera", () => {
  assert.equal(esperaDe429({ reintentar_en_segundos: 30 }, "90"), 30);
  assert.equal(esperaDe429({ reintentar_en_segundos: 2.2 }, null), 3);
  assert.equal(esperaDe429({}, "90"), 90);
  assert.equal(esperaDe429({ reintentar_en_segundos: "30" }, "90"), 90);
  assert.equal(esperaDe429({ reintentar_en_segundos: 0 }, null), null);
});

test("el mensaje dice la espera como el gateway", () => {
  const base = "Hiciste demasiadas peticiones en poco tiempo.";
  assert.equal(mensajeDeEspera(1), `${base} Vuelve a intentarlo en 1 segundo.`);
  assert.equal(mensajeDeEspera(59), `${base} Vuelve a intentarlo en 59 segundos.`);
  assert.equal(mensajeDeEspera(60), `${base} Vuelve a intentarlo en 1 minuto.`);
  assert.equal(mensajeDeEspera(61), `${base} Vuelve a intentarlo en 2 minutos.`);
  assert.equal(mensajeDeEspera(600), `${base} Vuelve a intentarlo en 10 minutos.`);
  assert.equal(mensajeDeEspera(null), `${base} Espera un momento y vuelve a intentarlo.`);
});

test("un 429 del gateway queda como vino", () => {
  const cuerpo = {
    error: "demasiadas_peticiones",
    mensaje: "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 9 segundos.",
    reintentar_en_segundos: 9,
  };
  assert.deepEqual(conEspera(429, cuerpo, "9"), cuerpo);
});

test("un 429 sin cuerpo se completa con la cabecera", () => {
  assert.deepEqual(conEspera(429, {}, "120"), {
    error: "demasiadas_peticiones",
    mensaje: "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 2 minutos.",
    reintentar_en_segundos: 120,
  });
  assert.deepEqual(conEspera(429, {}, null), {
    error: "demasiadas_peticiones",
    mensaje: "Hiciste demasiadas peticiones en poco tiempo. Espera un momento y vuelve a intentarlo.",
  });
});

test("otro estado no se toca", () => {
  const cuerpo = { error: "trabajo_no_existe", mensaje: "No existe." };
  assert.equal(conEspera(404, cuerpo, "30"), cuerpo);
  assert.deepEqual(conEspera(503, {}, "30"), {});
});
