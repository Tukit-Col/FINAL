// Lo que el acudiente lee sobre su retracto: la fecha limite cuando ya le llego
// el pedido, el aviso de que el plazo empieza con la entrega, y por que no puede
// cuando no puede. `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { textoDeRetracto } from "../src/lib/retracto.ts";
import type { EstadoRetracto } from "@tukit/contrato";

const base: EstadoRetracto = {
  puede: true,
  razon: null,
  vence_en: null,
  antes_de_entrega: false,
  solicitado_en: null,
};

test("entregado y dentro del plazo: dice hasta cuando y ofrece pedirlo", () => {
  const r = textoDeRetracto({ ...base, vence_en: "2026-03-12T04:59:59+00:00" });
  assert.equal(r.puedePedir, true);
  // 04:59 UTC del 12 es el 11 en Colombia: la fecha limite es la de Bogota.
  assert.match(r.frase, /11 de marzo de 2026/);
  assert.doesNotMatch(r.frase, /12 de marzo/);
  assert.match(r.frase, /5 días hábiles/);
});

test("antes de la entrega no hay fecha limite: el plazo empieza al llegar", () => {
  const r = textoDeRetracto({ ...base, antes_de_entrega: true });
  assert.equal(r.puedePedir, true);
  assert.match(r.frase, /5 días hábiles/);
  assert.match(r.frase, /te devolvemos el pago/);
});

test("plazo vencido y ya solicitado no ofrecen el boton y lo explican", () => {
  const vencido = textoDeRetracto({ ...base, puede: false, razon: "plazo_vencido" });
  assert.equal(vencido.puedePedir, false);
  assert.match(vencido.frase, /ya terminó/);
  const hecho = textoDeRetracto({ ...base, puede: false, razon: "ya_solicitado" });
  assert.equal(hecho.puedePedir, false);
  assert.match(hecho.frase, /Ya pediste/);
});

test("sin dato de retracto no se pinta nada", () => {
  assert.deepEqual(textoDeRetracto(undefined), { frase: "", puedePedir: false });
});
