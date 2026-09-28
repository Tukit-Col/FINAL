// La sesion del lado del servidor.
//
// El token vive en una cookie httpOnly que solo ponen y borran los Route
// Handlers: el navegador nunca lo ve en JavaScript, la misma disciplina de
// "solo servidor" que ya impone `servidor.ts`. Los Server Components leen la
// sesion con `sesionActual()`; la proteccion de rutas se hace en un layout con
// `redirect`, nunca en codigo de cliente.
//
// Que todo pase por `origenDeDatos()` significa que ninguna pantalla toca el
// backend directo: la cookie es el bearer real de identidad/gateway y el flujo
// es el mismo en toda la app.

import "server-only";
import { cookies } from "next/headers";
import type { MisSolicitudes } from "@tukit/contrato";
import {
  origenDeDatos,
  type MatriculaAcudiente,
  type Sesion,
} from "@tukit/contrato/servidor";

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

/**
 * Las matriculas vigentes del portador de la cookie, para precargar `/empezar`
 * cuando el acudiente ya tiene cuenta. Devuelve colegio+grado+anio y el `apodo`
 * del propio portador (el padre ve el de SUS hijos, para no re-teclearlo); sigue
 * sin traer nombre legal, documento ni estudiante_id, tal como los expone
 * `GET /v1/cuenta/matriculas`.
 *
 * Fail-closed a lista vacia, igual que `sesionActual()`: sin cookie, con token
 * rechazado o si el backend no responde, el formulario simplemente arranca sin
 * precarga en vez de romper la pantalla.
 */
export async function matriculasDeLaSesion(): Promise<MatriculaAcudiente[]> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return [];
  try {
    return await origenDeDatos().matriculasDelAcudiente(token);
  } catch {
    return [];
  }
}

/**
 * Las solicitudes del portador de la cookie —sus listas subidas + sus trabajos,
 * unidas— para la seccion "Mis solicitudes" del panel.
 *
 * A DIFERENCIA de `matriculasDeLaSesion()`, esto NO traga el fallo del backend:
 * devuelve `[]` SOLO cuando no hay cookie (no hay a quien pedirle). Si
 * inteligencia o la sesion fallan, deja PROPAGAR el error, para que el panel
 * distinga "no tienes solicitudes" (lista vacia legitima) de "no pudimos
 * cargarlas" (aviso de error). Fallar cerrado a `[]` aqui mentiria: mostraria
 * "no tienes solicitudes" cuando en realidad no se pudieron leer.
 *
 * La caida de catalogo NO llega hasta aca: inteligencia la degrada a
 * `listas_disponibles: false` y devuelve los trabajos igual (§Decisiones 5).
 */
export async function solicitudesDeLaSesion(): Promise<MisSolicitudes> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return { solicitudes: [], listas_disponibles: true };
  return origenDeDatos().misSolicitudes(token);
}
