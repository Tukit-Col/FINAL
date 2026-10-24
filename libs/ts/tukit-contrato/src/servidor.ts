// El origen de datos.
//
// La app siempre habla con el backend real: los 7 microservicios a traves del
// gateway (`TUKIT_API_URL`, en local o en produccion). El resto de la
// aplicacion no sabe de esto: pide el origen y lo usa.
//
// Solo se importa desde codigo de servidor (Route Handlers y Server
// Components). El navegador nunca ve la URL del backend, que es la misma
// razon por la que el prototipo ya tenia un proxy en vez de un `rewrite`.

import "server-only";

import { headers } from "next/headers";
import { unstable_rethrow } from "next/navigation";

import { ClienteApi } from "./cliente-http";
import type { OrigenDatos } from "./origen";

export function urlApi(): string {
  const url = process.env["TUKIT_API_URL"];
  if (!url) {
    // Falla ruidosa a proposito: sin backend no hay app. Un valor por defecto
    // silencioso fue justo el bug que se arrastro (apuntaba a :8080 cuando el
    // gateway vive en :8010). El gateway local por omision es :8010.
    throw new Error(
      "TUKIT_API_URL no esta definida. Apuntala al gateway (local: http://localhost:8010).",
    );
  }
  return url;
}

/** Origen absoluto de la app interna (apps/admin). El salto entre apps es una
 *  redireccion absoluta a otro origen (ADR 0008), configurada por entorno y
 *  nunca hardcodeada en un componente. */
export function urlAdmin(): string {
  return process.env["TUKIT_ADMIN_URL"] ?? "http://localhost:3001";
}

/** Origen absoluto de la app publica (apps/web). Simetrico a `urlAdmin`: al
 *  salir del back-office (:3001) el usuario vuelve al login de la web (:3000),
 *  que es otro origen. Se resuelve en el servidor porque el back-office no
 *  expone URLs con `NEXT_PUBLIC_` al navegador. */
export function urlWeb(): string {
  return process.env["TUKIT_WEB_URL"] ?? "http://localhost:3000";
}

/** Lo que se reenvia de la peticion entrante: solo `X-Forwarded-For`, para que
 *  el limite de tasa del gateway cuente por la IP del cliente y no por la de
 *  este servidor (ADR 0047). Next la pone con la direccion de la conexion si no
 *  venia; si venia, la deja como esta, y un proxy delante tiene que agregar la
 *  IP real a la derecha. Fuera de una peticion no hay nada que reenviar. */
export async function cabecerasReenviadas(): Promise<Record<string, string>> {
  let entrantes: Headers;
  try {
    entrantes = await headers();
  } catch (causa) {
    // Las senales internas de Next (renderizado dinamico) son suyas.
    unstable_rethrow(causa);
    return {};
  }
  const reenviada = entrantes.get("x-forwarded-for");
  return reenviada ? { "X-Forwarded-For": reenviada } : {};
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
