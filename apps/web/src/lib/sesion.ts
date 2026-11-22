// La sesión del lado del servidor.
//
// Decisiones:
// - El token vive en una cookie httpOnly que solo ponen y borran los Route Handlers: el navegador nunca
//   lo ve en JavaScript.
// - Los Server Components leen la sesión con `sesionActual()`; la protección de rutas se hace en un
//   layout con `redirect`, nunca en código de cliente.

import "server-only";
import { cookies } from "next/headers";
import type { MisSolicitudes, Pedido } from "@tukit/contrato";
import {
  origenDeDatos,
  type MatriculaAcudiente,
  type Sesion,
} from "@tukit/contrato/servidor";
import { fallaCerradoSalvoLimite } from "./limite";

export const COOKIE_SESION = "tukit_sesion";

export async function tokenDeSesion(): Promise<string | undefined> {
  return (await cookies()).get(COOKIE_SESION)?.value;
}

export async function sesionActual(): Promise<Sesion | null> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return null;
  return fallaCerradoSalvoLimite(() => origenDeDatos().sesionActual(token), null);
}

export async function matriculasDeLaSesion(): Promise<MatriculaAcudiente[]> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return [];
  return fallaCerradoSalvoLimite(() => origenDeDatos().matriculasDelAcudiente(token), []);
}

export async function solicitudesDeLaSesion(): Promise<MisSolicitudes> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return { solicitudes: [], listas_disponibles: true };
  return origenDeDatos().misSolicitudes(token);
}

export async function pedidosDeLaSesion(): Promise<Pedido[]> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) return [];
  return origenDeDatos().misPedidos(token);
}
