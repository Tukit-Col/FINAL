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

import type { MatriculaAcudiente, RolAsignado, Sesion } from "../origen";

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

// ------------------------------------------------------------ matriculas
//
// La tenencia sembrada del acudiente, para el camino "ya tengo cuenta": mama
// tiene un hijo en Quinto del colegio piloto. El `colegio_id` es el codigo del
// corpus ("2.13"), el mismo que `colegios()` ofrece, para que la precarga de
// `/empezar` case con una opcion real del desplegable. El anio es fijo para que
// la demostracion sea determinista, y coincide con el que siembra `identidad`.
const ANIO_LECTIVO_DEMO = 2026;

const MATRICULAS_SEMBRADAS: Record<string, MatriculaAcudiente[]> = {
  "mama@ejemplo.com": [{ colegio_id: COLEGIO_PILOTO, grado: "Quinto", anio_lectivo: ANIO_LECTIVO_DEMO }],
};

// Los registros que llegan en tiempo de ejecucion por `registrarAcudiente`.
// Almacen de proceso, no persistente: el simulado no tiene base. Vive aqui para
// que `matriculasDelAcudiente` devuelva lo recien registrado igual que lo
// sembrado, y que el camino "soy nuevo usuario" sea coherente dentro de la demo.
const MATRICULAS_REGISTRADAS = new Map<string, MatriculaAcudiente[]>();

/** Guarda (en memoria) las matriculas de un alta simulada. */
export function registrarMatriculasSimuladas(
  correo: string,
  hijos: { colegio_id: string; grado: string }[],
): void {
  MATRICULAS_REGISTRADAS.set(
    correo.trim().toLowerCase(),
    hijos.map((h) => ({
      colegio_id: h.colegio_id,
      grado: h.grado,
      anio_lectivo: ANIO_LECTIVO_DEMO,
    })),
  );
}

/** Las matriculas de un correo: primero lo registrado en vivo, si no lo sembrado. */
export function matriculasDeCorreo(correo: string): MatriculaAcudiente[] {
  const clave = correo.trim().toLowerCase();
  return MATRICULAS_REGISTRADAS.get(clave) ?? MATRICULAS_SEMBRADAS[clave] ?? [];
}
