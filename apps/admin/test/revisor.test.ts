// Prueba de la carga del revisor de una lista (`lib/revisor`): qué errores
// tumban la página (`notFound`) y cuáles no. Mismo patrón que
// `atributos-editor.test.ts`: lógica pura, `node --test` con type-stripping.
//
// Correr:  node --test test/revisor.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type {
  Catalogo,
  PercepcionCruda,
  RevisionLista,
  VistaPreviaLista,
} from "@tukit/contrato";
import { cargarRevisor, type OrigenRevisor } from "../src/lib/revisor.ts";

// Un error con la forma de `ErrorTukit` (estado + codigo); el módulo los
// reconoce por su forma, no por su clase.
function fallo(estado: number, codigo: string): Error {
  return Object.assign(new Error(codigo), { estado, codigo });
}

const REVISION = { version_id: "v1" } as unknown as RevisionLista;
const PERCEPCION = { paginas: [] } as unknown as PercepcionCruda;
const CATALOGO = { productos: [] } as unknown as Catalogo;
const VISTA_PREVIA: VistaPreviaLista = {
  trabajo_id: "t1",
  estado: "espera_revision",
  creado_en: null,
  lineas_sin_decidir: 2,
};

function origen(cambios: Partial<Record<keyof OrigenRevisor, () => Promise<unknown>>> = {}) {
  const base: Record<keyof OrigenRevisor, () => Promise<unknown>> = {
    revisionLista: async () => REVISION,
    percepcion: async () => PERCEPCION,
    catalogo: async () => CATALOGO,
    vistaPreviaDeVersion: async () => null,
    ...cambios,
  };
  return base as unknown as OrigenRevisor;
}

test("con documento trae todo", async () => {
  const datos = await cargarRevisor(origen(), "v1");
  assert.deepEqual(datos, {
    revision: REVISION,
    percepcion: PERCEPCION,
    catalogo: CATALOGO,
    vistaPrevia: null,
  });
});

test("sin documento original (sin_evidencia) el revisor abre igual", async () => {
  const datos = await cargarRevisor(
    origen({ percepcion: async () => Promise.reject(fallo(404, "sin_evidencia")) }),
    "v1",
  );
  assert.ok(datos);
  assert.equal(datos.percepcion, null);
  assert.equal(datos.revision, REVISION);
});

test("solo version_no_existe es notFound", async () => {
  const deRevision = await cargarRevisor(
    origen({ revisionLista: async () => Promise.reject(fallo(404, "version_no_existe")) }),
    "v1",
  );
  assert.equal(deRevision, null);

  const dePercepcion = await cargarRevisor(
    origen({ percepcion: async () => Promise.reject(fallo(404, "version_no_existe")) }),
    "v1",
  );
  assert.equal(dePercepcion, null);
});

test("cualquier otro error se relanza", async () => {
  await assert.rejects(
    cargarRevisor(origen({ percepcion: async () => Promise.reject(fallo(503, "remoto_caido")) }), "v1"),
    /remoto_caido/,
  );
  await assert.rejects(
    cargarRevisor(origen({ revisionLista: async () => Promise.reject(fallo(500, "interno")) }), "v1"),
    /interno/,
  );
  await assert.rejects(
    cargarRevisor(origen({ catalogo: async () => Promise.reject(fallo(503, "remoto_caido")) }), "v1"),
    /remoto_caido/,
  );
});

test("la vista previa se trae, y si falla no tumba el revisor", async () => {
  const con = await cargarRevisor(origen({ vistaPreviaDeVersion: async () => VISTA_PREVIA }), "v1");
  assert.equal(con?.vistaPrevia, VISTA_PREVIA);

  const caida = await cargarRevisor(
    origen({ vistaPreviaDeVersion: async () => Promise.reject(fallo(503, "remoto_caido")) }),
    "v1",
  );
  assert.ok(caida);
  assert.equal(caida.vistaPrevia, null);
});
