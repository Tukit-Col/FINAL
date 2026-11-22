import "server-only";
import { cookies } from "next/headers";
import { origenDeDatos } from "@tukit/contrato/servidor";

export const COOKIE_SESION = "tukit_sesion";

export async function tokenDeSesion(): Promise<string | undefined> {
  return (await cookies()).get(COOKIE_SESION)?.value;
}

export async function quienSoy(): Promise<{ usuarioId: string; esAdmin: boolean } | null> {
  const token = await tokenDeSesion();
  if (!token) return null;
  try {
    const sesion = await origenDeDatos().sesionActual(token);
    if (!sesion) return null;
    return { usuarioId: sesion.usuario_id, esAdmin: sesion.roles.some((r) => r.rol === "admin") };
  } catch {
    return null;
  }
}
