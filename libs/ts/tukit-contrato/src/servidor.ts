// La bandera.
//
// Una sola variable de entorno decide si las pantallas hablan con el backend
// real o con las semillas del repositorio. El resto de la aplicacion no la
// consulta nunca: pide el origen y lo usa.
//
//   TUKIT_ORIGEN_DATOS=simulado   (por defecto) lee datos/catalogo y el corpus
//   TUKIT_ORIGEN_DATOS=api        habla con TUKIT_API_URL sobre /v1
//
// Solo se importa desde codigo de servidor (Route Handlers y Server
// Components). El navegador nunca ve la URL del backend, que es la misma
// razon por la que el prototipo ya tenia un proxy en vez de un `rewrite`.

import "server-only";

import { ClienteApi } from "./cliente-http";
import type { OrigenDatos } from "./origen";
import { OrigenSimulado } from "./simulado/origen-simulado";
import { rutaDelAlmacen } from "./simulado/almacen";

export type NombreOrigen = "api" | "simulado";

export function origenConfigurado(): NombreOrigen {
  return process.env["TUKIT_ORIGEN_DATOS"] === "api" ? "api" : "simulado";
}

export function urlApi(): string {
  return process.env["TUKIT_API_URL"] ?? "http://localhost:8080";
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

let cache: OrigenDatos | null = null;

export function origenDeDatos(): OrigenDatos {
  if (cache) return cache;
  cache =
    origenConfigurado() === "api"
      ? new ClienteApi({ urlBase: urlApi() })
      : new OrigenSimulado();
  return cache;
}

/** Lo que la UI muestra en la cinta de estado, para que nadie confunda los dos modos. */
export function descripcionOrigen(): { nombre: NombreOrigen; detalle: string } {
  return origenConfigurado() === "api"
    ? { nombre: "api", detalle: urlApi() }
    : { nombre: "simulado", detalle: rutaDelAlmacen() };
}

export { ErrorTukit, destinoDe } from "./origen";
export type {
  OrigenDatos,
  Rol,
  RolAsignado,
  Sesion,
  Credenciales,
  MatriculaAcudiente,
  RegistroAcudiente,
} from "./origen";
