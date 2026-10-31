// Pruebas del sondeo de la pantalla de espera: la consulta del trabajo lleva el
// token de la sesion, para que el limite por cuenta del gateway (ADR 0047) la
// cuente y la pantalla pueda mostrar su aviso; sin sesion sigue anonima.
// Runner nativo de Node (type-stripping): `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { consultarTrabajoDelPortador } from "../src/lib/sondeo.ts";

function origenQueAnota() {
  const llamadas: { trabajoId: string; token: string | undefined }[] = [];
  return {
    llamadas,
    async consultarTrabajo(trabajoId: string, token?: string) {
      llamadas.push({ trabajoId, token });
      return { trabajo_id: trabajoId };
    },
  };
}

test("con sesion, la consulta viaja con el token", async () => {
  const origen = origenQueAnota();
  await consultarTrabajoDelPortador(origen, "t-1", "tok-mama");
  assert.deepEqual(origen.llamadas, [{ trabajoId: "t-1", token: "tok-mama" }]);
});

test("sin sesion (ruta rapida anonima), la consulta sigue sin token", async () => {
  const origen = origenQueAnota();
  const trabajo = await consultarTrabajoDelPortador(origen, "t-2", undefined);
  assert.deepEqual(origen.llamadas, [{ trabajoId: "t-2", token: undefined }]);
  assert.deepEqual(trabajo, { trabajo_id: "t-2" });
});
