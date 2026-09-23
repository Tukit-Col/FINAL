// `POST /api/sesion` (entrar) y `DELETE /api/sesion` (salir).
//
// Es el unico punto donde se pone y se borra la cookie de sesion, por la misma
// razon que `/api/trabajos`: el navegador no habla con el backend, el token no
// sale al cliente, y aqui se decide si la peticion va al backend real
// (gateway→identidad) o al origen simulado. Devuelve a donde ir despues, no el
// token.

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
  let cred: Credenciales;
  try {
    cred = (await peticion.json()) as Credenciales;
  } catch {
    return NextResponse.json(
      { error: "peticion_invalida", mensaje: "No pudimos leer el correo y la clave." },
      { status: 400 },
    );
  }

  try {
    const { sesion, token } = await origenDeDatos().iniciarSesion(cred);
    const destino = destinoDe(sesion);

    // El destino logico se traduce a una URL. La app interna vive en otro
    // origen (:3001) y el salto es una redireccion absoluta configurada por
    // entorno; el colegio y el acudiente viven en esta misma app.
    const url = destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta;

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
    // Cerrar es idempotente: si el backend no responde, igual borramos la
    // cookie de este lado.
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
