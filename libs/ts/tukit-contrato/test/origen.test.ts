import { test } from "node:test";
import assert from "node:assert/strict";
import type { AcudienteResumen, NuevaCuenta, OrigenDatos, Sesion } from "../src/origen.ts";
import type { SubidaHecha, SubidaListas, TrabajoResumen } from "../src/contrato.ts";

const origenDeAlta: Pick<OrigenDatos, "crearCuenta"> = {
  async crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }> {
    const sesion: Sesion = {
      usuario_id: "usr-1",
      correo: cuenta.correo,
      nombre: cuenta.nombre,
      roles: [],
      version_permisos: 1,
    };
    return { sesion, token: "tok-1" };
  },
};

test("crearCuenta devuelve sesion y token, como iniciarSesion", async () => {
  const nueva: NuevaCuenta = {
    correo: "ana@ej.com",
    clave: "clave-fuerte",
    nombre: "Ana",
    celular: "+57 300 000 0000",
  };
  const { sesion, token } = await origenDeAlta.crearCuenta(nueva);
  assert.equal(sesion.correo, "ana@ej.com");
  assert.ok(token.length > 0);
});

const origenDelAcudiente: Pick<OrigenDatos, "misTrabajos"> = {
  async misTrabajos(_token?: string): Promise<TrabajoResumen[]> {
    return [
      {
        trabajo_id: "t1",
        estado: "encolado",
        creado_en: "2026-09-01T00:00:00Z",
        hijos: [{ referencia: "hijo-0", colegio_id: "c1", grado: "Cuarto" }],
        preferencias: { disposicion_sobreprecio: 0.2 },
      },
    ];
  },
};

test("misTrabajos devuelve las solicitudes del acudiente", async () => {
  const filas = await origenDelAcudiente.misTrabajos("tok-acud");
  assert.equal(filas.length, 1);
  assert.equal(filas[0]!.estado, "encolado");
  assert.equal(filas[0]!.hijos[0]!.grado, "Cuarto");
  assert.equal(filas[0]!.hijos[0]!.referencia, "hijo-0");
});

const origenDelAdmin: Pick<OrigenDatos, "acudientesDeColegio"> = {
  async acudientesDeColegio(_colegioId: string): Promise<AcudienteResumen[]> {
    return [
      { usuario_id: "u1", estado: "procesando", actualizado_en: "2026-09-01T00:00:00Z", trabajo_id: "t1" },
      { usuario_id: "u2", estado: "espera_revision", actualizado_en: "2026-09-01T01:00:00Z", trabajo_id: "t2" },
    ];
  },
};

test("acudientesDeColegio devuelve resúmenes con estado y sin datos de menores", async () => {
  const filas = await origenDelAdmin.acudientesDeColegio("colegio-1");
  assert.equal(filas.length, 2);
  assert.equal(filas[0]!.estado, "procesando");
  assert.equal(filas[1]!.usuario_id, "u2");
  assert.deepEqual(Object.keys(filas[0]!).sort(), [
    "actualizado_en",
    "estado",
    "trabajo_id",
    "usuario_id",
  ]);
});

function origenQueSube(subidas: SubidaHecha[]): Pick<OrigenDatos, "subirListas"> {
  return {
    async subirListas(): Promise<SubidaListas> {
      return { subidas, contacto_referencia: "c-ficticio-1" };
    },
  };
}

test("con el catalogo arriba cada hijo queda ligado a su version", async () => {
  const origen = origenQueSube([{ referencia: "hijo-0", version_id: "v-1", grado: "Cuarto" }]);
  const { subidas } = await origen.subirListas([], []);
  assert.equal(subidas[0]?.version_id, "v-1");
  assert.equal(subidas[0]?.estado, undefined);
});

test("con el catalogo caido la lista queda recibida y pendiente, sin version", async () => {
  const origen = origenQueSube([
    { referencia: "hijo-0", version_id: "v-1", grado: "Cuarto" },
    { referencia: "hijo-1", version_id: null, grado: "Quinto", estado: "pendiente" },
  ]);
  const { subidas } = await origen.subirListas([], []);
  const pendientes = subidas.filter((s: SubidaHecha) => s.estado === "pendiente");
  assert.equal(pendientes.length, 1);
  assert.equal(pendientes[0]?.referencia, "hijo-1");
  assert.equal(pendientes[0]?.version_id, null);
});
