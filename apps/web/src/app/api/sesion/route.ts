import { NextResponse } from "next/server";
import {
  destinoDe,
  origenDeDatos,
  urlAdmin,
  type Credenciales,
} from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cred: Credenciales & { destino?: string };
  try {
    cred = (await peticion.json()) as Credenciales & { destino?: string };
  } catch {
    return NextResponse.json(
      { error: "peticion_invalida", mensaje: "No pudimos leer el correo y la clave." },
      { status: 400 },
    );
  }

  try {
    const { sesion, token } = await origenDeDatos().iniciarSesion(cred);
    const destino = destinoDe(sesion);

    let url = destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta;

    if (cred.destino && cred.destino.startsWith("/") && !cred.destino.startsWith("//")) {
      url = cred.destino;
    }

    const respuesta = NextResponse.json({ nombre: sesion.nombre, roles: sesion.roles, url });
    respuesta.cookies.set(COOKIE_SESION, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 8,
    });
    return respuesta;
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function DELETE(peticion: Request): Promise<Response> {
  const token = leerCookie(peticion, COOKIE_SESION);
  try {
    if (token) await origenDeDatos().cerrarSesion(token);
  } catch {
  }
  const respuesta = NextResponse.json({ ok: true });
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
