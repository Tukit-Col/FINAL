// Prueba de la guarda de "Aprobar y publicar" (`lib/aprobar`).
//
// Correr:  node --test test/aprobar.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { VistaPreviaLista } from "@tukit/contrato";
import { guardaDeAprobacion } from "../src/lib/aprobar.ts";

function previa(cambios: Partial<VistaPreviaLista> = {}): VistaPreviaLista {
  return {
    trabajo_id: "t1",
    estado: "espera_revision",
    creado_en: "2026-10-01T00:00:00Z",
    lineas_sin_decidir: 0,
    desactualizada: false,
    ...cambios,
  };
}

test("una vista previa al día y sin dudosas deja aprobar sin más", () => {
  assert.deepEqual(guardaDeAprobacion(previa(), false), { tipo: "libre" });
});

test("con dudosas pide confirmar y enlaza a la vista previa", () => {
  const guarda = guardaDeAprobacion(previa({ lineas_sin_decidir: 3 }), true);
  assert.deepEqual(guarda, {
    tipo: "confirmar",
    mensaje:
      "Quedan 3 dudosas. La lista se aprueba, pero el kit queda en la Cola hasta que las decidas.",
    trabajoId: "t1",
  });
});

test("desactualizada bloquea, aunque tenga dudosas", () => {
  const guarda = guardaDeAprobacion(previa({ desactualizada: true, lineas_sin_decidir: 2 }), false);
  assert.deepEqual(guarda, {
    tipo: "bloqueada",
    mensaje: "La lista cambió después de previsualizar: vuelve a previsualizar",
  });
});

test("sin vista previa solo informa, según haya o no acudiente", () => {
  assert.deepEqual(guardaDeAprobacion(null, false), {
    tipo: "aviso",
    mensaje: "Sin vista previa: al aprobar se arma un kit nuevo que quedará en la Cola para revisar.",
  });
  assert.deepEqual(guardaDeAprobacion(null, true), {
    tipo: "aviso",
    mensaje:
      "Sin vista previa: al aprobar se arma el kit del acudiente desde cero y se le publica directo.",
  });
});

test("si no se pudo leer la vista previa no afirma que no la hay", () => {
  const guarda = guardaDeAprobacion(undefined, false);
  assert.equal(guarda.tipo, "aviso");
  assert.match((guarda as { mensaje: string }).mensaje, /No pudimos leer la vista previa/);
});
