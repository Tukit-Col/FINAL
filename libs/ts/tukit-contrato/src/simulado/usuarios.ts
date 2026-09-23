// Usuarios sembrados para el origen simulado.
//
// Misma disciplina que `semillas.ts`: datos versionados en el repositorio, no
// inventados en tiempo de ejecucion. Cada fila mapea un correo a uno o mas
// roles sobre un ambito, y el ambito del acudiente apunta a un `colegio_id`
// que existe de verdad en el corpus (2.13 = Colegio Agustiniano Ciudad
// Salitre, el del piloto), para que la historia de alcance sea coherente con
// lo que `identidad` devolveria (ADR 0013).
//
// El simulado NO verifica la clave: `identidad` hoy tampoco tiene una
// credencial utilizable (api.py sella `clave_hash="sin-credencial"`). Se acepta
// cualquier clave para un correo sembrado y se dice en pantalla, para no fingir
// un control de acceso que el backend todavia no ofrece.

import type { RolAsignado, Sesion } from "../origen";

/** Una fila sembrada: quien es y que roles tiene, tal como los daria identidad. */
export interface UsuarioSimulado {
  usuario_id: string;
  correo: string;
  nombre: string;
  roles: RolAsignado[];
  version_permisos: number;
}

// El colegio del piloto, para anclar el ambito del acudiente en algo real.
const COLEGIO_PILOTO = "2.13";

export const USUARIOS: UsuarioSimulado[] = [
  {
    usuario_id: "usr-mama",
    correo: "mama@ejemplo.com",
    nombre: "Mamá de ejemplo",
    roles: [{ rol: "acudiente", ambito: { tipo: "colegio", id: COLEGIO_PILOTO } }],
    version_permisos: 1,
  },
  {
    usuario_id: "usr-papa",
    correo: "papa@ejemplo.com",
    nombre: "Papá de ejemplo",
    roles: [{ rol: "acudiente", ambito: { tipo: "colegio", id: COLEGIO_PILOTO } }],
    version_permisos: 1,
  },
  {
    usuario_id: "usr-rectoria",
    correo: "rectoria@colegio.edu.co",
    nombre: "Rectoría del colegio",
    roles: [{ rol: "colegio_admin", ambito: { tipo: "colegio", id: COLEGIO_PILOTO } }],
    version_permisos: 1,
  },
  {
    usuario_id: "usr-docente",
    correo: "docente@colegio.edu.co",
    nombre: "Docente del colegio",
    roles: [{ rol: "colegio_docente", ambito: { tipo: "colegio", id: COLEGIO_PILOTO } }],
    version_permisos: 1,
  },
  {
    usuario_id: "usr-operador",
    correo: "operador@tukit.co",
    nombre: "Operador Tukit",
    roles: [{ rol: "operador", ambito: { tipo: "global", id: null } }],
    version_permisos: 1,
  },
  {
    usuario_id: "usr-admin",
    correo: "admin@tukit.co",
    nombre: "Admin Tukit",
    roles: [{ rol: "admin", ambito: { tipo: "global", id: null } }],
    version_permisos: 1,
  },
];

const POR_CORREO = new Map(USUARIOS.map((u) => [u.correo, u]));

export function usuarioPorCorreo(correo: string): UsuarioSimulado | null {
  return POR_CORREO.get(correo.trim().toLowerCase()) ?? null;
}

/** Arma la Sesion publica a partir de una fila sembrada. */
export function sesionDe(u: UsuarioSimulado): Sesion {
  return {
    usuario_id: u.usuario_id,
    correo: u.correo,
    nombre: u.nombre,
    roles: u.roles,
    version_permisos: u.version_permisos,
  };
}

// Token de demostracion: base64 del correo, deliberadamente SIN firma real,
// para que nadie lo confunda con el bearer que emite identidad/gateway en el
// modo `api`. Es transparente a proposito.
export function tokenSimulado(correo: string): string {
  return `sim.${Buffer.from(correo, "utf8").toString("base64url")}`;
}

export function leerTokenSimulado(token: string): string | null {
  if (!token.startsWith("sim.")) return null;
  try {
    return Buffer.from(token.slice(4), "base64url").toString("utf8");
  } catch {
    return null;
  }
}
