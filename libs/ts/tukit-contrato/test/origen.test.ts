// El contrato de alta de cuenta del acudiente: `crearCuenta` devuelve la misma
// forma que `iniciarSesion` ({sesion, token}). Se fija con un doble tipado como
// `Pick<OrigenDatos, "crearCuenta">` — TS verifica que la firma calce con la
// interfaz sin obligar a stubear los ~40 metodos restantes del origen.
//
// Runner nativo de Node sobre TypeScript (type-stripping, Node 24), sin
// dependencias. Correr: `node --test test/cuenta.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { NuevaCuenta, OrigenDatos, Sesion } from "../src/origen.ts";

// ponytail: doble de prueba, solo `crearCuenta` se ejerce aqui.
const origen: Pick<OrigenDatos, "crearCuenta"> = {
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

test("crearCuenta devuelve sesion y token", async () => {
  const nueva: NuevaCuenta = {
    correo: "ana@ej.com",
    clave: "clave-fuerte",
    nombre: "Ana",
    celular: "+57 300 000 0000",
  };
  const { sesion, token } = await origen.crearCuenta(nueva);
  assert.equal(sesion.correo, "ana@ej.com");
  assert.ok(token.length > 0);
});
