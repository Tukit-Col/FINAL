// Las opciones con que se abre el widget de Wompi. Runner nativo de Node:
// `node --test apps/web/test/wompi.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { opcionesWidget } from "../src/lib/wompi.ts";

const base = {
  publicKey: "pub_test_x",
  currency: "COP",
  amountInCents: 900000,
  reference: "tukit-1",
  signature: { integrity: "abc" },
  redirectUrl: "http://localhost:3000/pago/resultado",
};

test("el widget se abre por postMessage para que el redirectUrl no viaje en la URL", () => {
  // Por omision el widget serializa la configuracion en la URL de su iframe, y
  // el CDN de Wompi responde 403 si ahi aparece un redirect-url a localhost: el
  // iframe nunca carga y el modal se queda en "cargando".
  const opciones = opcionesWidget(base);
  assert.equal(opciones.bootstrapTransport, "postmessage");
  assert.equal(opciones.redirectUrl, "http://localhost:3000/pago/resultado");
  assert.equal(opciones.reference, "tukit-1");
});
