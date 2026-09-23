// `DELETE /api/sesion` — salir del back-office.
//
// El back-office no pone la cookie de sesion (eso lo hace la app web al entrar,
// antes de saltar aqui), pero si tiene que poder borrarla: la cookie es
// httpOnly, asi que el cliente no puede tocarla solo. Igual que en la web,
// avisamos a identidad (`cerrarSesion`) por consistencia y borramos la cookie
// de este lado. El token no sale nunca al navegador; se queda del lado del
// servidor, como el resto de llamadas al backend.

import { NextResponse } from "next/server";
import { origenDeDatos, urlWeb } from "@tukit/contrato/servidor";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function DELETE(peticion: Request): Promise<Response> {
  const token = leerCookie(peticion, COOKIE_SESION);
  try {
    if (token) await origenDeDatos().cerrarSesion(token);
  } catch {
    // Cerrar es idempotente (ADR 0016: el token es autocontenido, sin estado de
    // servidor que invalidar). Si identidad no responde, igual borramos la
    // cookie de este lado para que el usuario salga.
  }
  // Al salir del back-office se vuelve al login de la web (:3000), que es otro
  // origen; el destino se decide aqui, del lado del servidor, porque el
  // navegador no conoce esa URL (no hay `NEXT_PUBLIC_`).
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
