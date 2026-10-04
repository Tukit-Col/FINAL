// Prueba de cómo se arma la cola (`lib/cola`): una fila por lista pendiente,
// con su vista previa o su kit del grado como estado, y los kits de acudientes
// aparte. El inicio cuenta con los mismos `conteos`.
//
// Correr:  node --test test/cola.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { EntradaCola, EstadoTrabajo, VersionListaAdmin } from "@tukit/contrato";
import { armarCola, textoEstadoLista } from "../src/lib/cola.ts";

function entrada(
  trabajo_id: string,
  origen: string,
  cambios: Partial<EntradaCola> = {},
): EntradaCola {
  return {
    trabajo_id,
    estado: "espera_revision" as EstadoTrabajo,
    recibido_en: "2026-10-01T00:00:00Z",
    hijos: 1,
    lineas_totales: 3,
    lineas_pendientes: 1,
    colegios: ["c1"],
    grados: ["5"],
    origen,
    version_id: null,
    usuario_id: null,
    lineas_sin_decidir: 0,
    huecos: 0,
    acudientes_esperando: 0,
    ...cambios,
  };
}

function version(version_id: string, cambios: Partial<VersionListaAdmin> = {}): VersionListaAdmin {
  return {
    version_id,
    colegio_id: "c1",
    grado: "5",
    anio_lectivo: 2026,
    numero: 1,
    revisada: false,
    items: 10,
    procedencia: "onboarding",
    tiene_contacto: false,
    colegio_nombre: null,
    ...cambios,
  };
}

test("una fila por lista, con el estado de su vista previa", () => {
  const { porVerificar } = armarCola({
    versiones: [version("sin"), version("dudosa"), version("lista")],
    entradas: [
      entrada("p1", "preview_onboarding", { version_id: "dudosa", lineas_sin_decidir: 2 }),
      entrada("p2", "preview_onboarding", { version_id: "lista" }),
    ],
  });
  assert.deepEqual(
    porVerificar.map((f) => [f.version?.version_id, textoEstadoLista(f.estado)]),
    [
      ["sin", "Sin vista previa"],
      ["dudosa", "Vista previa: 2 dudosas"],
      ["lista", "Lista para aprobar"],
    ],
  );
  assert.equal(porVerificar[1].vistaPrevia?.trabajo_id, "p1");
});

test("con dos vistas previas de la misma lista vale la más reciente", () => {
  const { porVerificar } = armarCola({
    versiones: [version("v")],
    entradas: [
      entrada("vieja", "preview_onboarding", { version_id: "v", recibido_en: "2026-10-01T00:00:00Z" }),
      entrada("nueva", "preview_onboarding", { version_id: "v", recibido_en: "2026-10-02T00:00:00Z" }),
    ],
  });
  assert.equal(porVerificar.length, 1);
  assert.equal(porVerificar[0].vistaPrevia?.trabajo_id, "nueva");
});

test("la vista previa de una lista que ya no está pendiente no se muestra", () => {
  const cola = armarCola({
    versiones: [],
    entradas: [entrada("p", "preview_onboarding", { version_id: "cerrada", lineas_sin_decidir: 4 })],
  });
  assert.equal(cola.porVerificar.length, 0);
  assert.equal(cola.conteos.dudosasSinDecidir, 0);
});

test("el kit del grado sin papá va en la fila de su lista, o en una propia", () => {
  const { porVerificar } = armarCola({
    versiones: [version("v")],
    entradas: [
      entrada("k1", "colegio_grado", { version_id: "v", lineas_sin_decidir: 1 }),
      entrada("k2", "colegio_grado", { version_id: "cerrada", lineas_sin_decidir: 3, acudientes_esperando: 1 }),
    ],
  });
  assert.equal(porVerificar.length, 2);
  // La que tiene un papá esperando va primero.
  assert.equal(porVerificar[0].version, null);
  assert.equal(porVerificar[0].kitDelGrado?.trabajo_id, "k2");
  assert.equal(textoEstadoLista(porVerificar[0].estado), "Lista verificada · kit con 3 dudosas");
  assert.equal(porVerificar[1].version?.version_id, "v");
  assert.equal(porVerificar[1].kitDelGrado?.trabajo_id, "k1");
});

test("primero las listas con acudiente esperando, después por renglones", () => {
  const { porVerificar } = armarCola({
    versiones: [
      version("corta", { items: 3 }),
      version("larga", { items: 30 }),
      version("padre", { items: 1, tiene_contacto: true }),
    ],
    entradas: [],
  });
  assert.deepEqual(
    porVerificar.map((f) => f.version?.version_id),
    ["padre", "larga", "corta"],
  );
});

test("los kits de acudientes van aparte y la cuenta es la misma del inicio", () => {
  const cola = armarCola({
    versiones: [version("v")],
    entradas: [
      entrada("p", "preview_onboarding", { version_id: "v", lineas_sin_decidir: 2 }),
      entrada("a", "lista_verificada", { usuario_id: "u1", lineas_sin_decidir: 1 }),
      entrada("pub", "lista_verificada", { usuario_id: "u2", estado: "publicado", lineas_sin_decidir: 5 }),
    ],
  });
  assert.deepEqual(
    cola.deAcudientes.map((e) => e.trabajo_id),
    ["a"],
  );
  assert.deepEqual(cola.conteos, { listasPorVerificar: 1, kitsDeAcudientes: 1, dudosasSinDecidir: 3 });
});

test("sin nada pendiente, todo en cero", () => {
  const cola = armarCola({ versiones: [], entradas: [] });
  assert.deepEqual(cola.conteos, { listasPorVerificar: 0, kitsDeAcudientes: 0, dudosasSinDecidir: 0 });
  assert.deepEqual(cola.deAcudientes, []);
});
