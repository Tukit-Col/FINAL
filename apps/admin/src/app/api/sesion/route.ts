import { NextResponse } from "next/server";
import { origenDeDatos, urlWeb } from "@tukit/contrato/servidor";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function DELETE(peticion: Request): Promise<Response> {
  const token = leerCookie(peticion, COOKIE_SESION);
  try {
    if (token) await origenDeDatos().cerrarSesion(token);
  } catch {
  }
  const respuesta = NextResponse.json({ ok: true, url: `${urlWeb()}/ingresar` });
  respuesta.cookies.delete(COOKIE_SESION);
  return respuesta;
}

function leerCookie(peticion: Request, nombre: string): string | null {
  const crudo = peticion.headers.get("cookie");
  if (!crudo) return null;
  for (const par of crudo.split(";")) {
    const [k, ...v] = par.trim().split("=");
    if (k === nombre) return decodeURIComponent(v.join("="));
  }
  return null;
}
