// La sesion del lado del servidor.
//
// El token vive en una cookie httpOnly que solo ponen y borran los Route
// Handlers: el navegador nunca lo ve en JavaScript, la misma disciplina de
// "solo servidor" que ya impone `servidor.ts`. Los Server Components leen la
// sesion con `sesionActual()`; la proteccion de rutas se hace en un layout con
// `redirect`, nunca en codigo de cliente.
//
// Que todo pase por `origenDeDatos()` significa que cambiar `TUKIT_ORIGEN_DATOS`
// no toca ninguna pantalla: en `simulado` la cookie es el sello base64, en
// `api` es el bearer real de identidad/gateway. Mismo nombre, mismo flujo.

import "server-only";
import { cookies } from "next/headers";
import { origenDeDatos, type Sesion } from "@tukit/contrato/servidor";

export const COOKIE_SESION = "tukit_sesion";

/** La sesion actual, o `null` si no hay cookie o el token ya no vale. */
export async function sesionActual(): Promise<Sesion | null> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return null;
  try {
    return await origenDeDatos().sesionActual(token);
  } catch {
    // Un token que el backend rechaza es como no tener sesion: fail-closed,
    // igual que `puede()`.
    return null;
  }
}
