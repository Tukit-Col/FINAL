// El origen de datos de las apps, solo para código de servidor.
//
// Decisiones:
// - Las apps hablan siempre con el backend real, a través del gateway (`TUKIT_API_URL`).
// - Solo se importa desde Route Handlers y Server Components: el navegador nunca ve la URL del
//   backend, y una `rewrite` de Next cortaría a los 30 s las peticiones largas del pipeline.

import "server-only";

import { cookies, headers } from "next/headers";
import { unstable_rethrow } from "next/navigation";

import { ClienteApi } from "./cliente-http";
import { autorizacionDeConsola, esRutaDeConsola } from "./consola";
import type { OrigenDatos } from "./origen";

export function urlApi(): string {
  const url = process.env["TUKIT_API_URL"];
  if (!url) {
    throw new Error(
      "TUKIT_API_URL no esta definida. Apuntala al gateway (local: http://localhost:8010).",
    );
  }
  return url;
}

export function urlAdmin(): string {
  return process.env["TUKIT_ADMIN_URL"] ?? "http://localhost:3001";
}

export function urlWeb(): string {
  return process.env["TUKIT_WEB_URL"] ?? "http://localhost:3000";
}

const COOKIE_SESION = "tukit_sesion";

export async function cabecerasReenviadas(ruta = ""): Promise<Record<string, string>> {
  let entrantes: Headers;
  let token: string | undefined;
  try {
    entrantes = await headers();
    if (esRutaDeConsola(ruta)) token = (await cookies()).get(COOKIE_SESION)?.value;
  } catch (causa) {
    unstable_rethrow(causa);
    return {};
  }
  const reenviada = entrantes.get("x-forwarded-for");
  return {
    ...(reenviada ? { "X-Forwarded-For": reenviada } : {}),
    ...autorizacionDeConsola(ruta, token),
  };
}

let cache: OrigenDatos | null = null;

export function origenDeDatos(): OrigenDatos {
  if (cache) return cache;
  cache = new ClienteApi({ urlBase: urlApi(), cabeceras: cabecerasReenviadas });
  return cache;
}

export { ErrorTukit, destinoDe } from "./origen";
export type {
  OrigenDatos,
  Rol,
  RolAsignado,
  Sesion,
  Credenciales,
  NuevaCuenta,
  MatriculaAcudiente,
  RegistroAcudiente,
  HijoNuevo,
  AcudienteAdmin,
  HijoAcudiente,
} from "./origen";
