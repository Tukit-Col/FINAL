// `POST /empezar/api/cuenta`: el paso 1 de /empezar crea la cuenta del acudiente.
//
// Mismo patron que `/api/sesion`: es el unico punto donde se pone la cookie de
// sesion tras el alta, el navegador no habla con el backend, y el token nunca
// sale al cliente. Devuelve la sesion (nombre/roles), no el token.

import { NextResponse } from "next/server";
import { origenDeDatos, type NuevaCuenta } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuenta: NuevaCuenta;
  try {
    cuenta = (await peticion.json()) as NuevaCuenta;
  } catch {
    return NextResponse.json(
      { error: "peticion_invalida", mensaje: "No pudimos leer los datos de la cuenta." },
      { status: 400 },
    );
  }

  try {
    const { sesion, token } = await origenDeDatos().crearCuenta(cuenta);
    const respuesta = NextResponse.json({ nombre: sesion.nombre, roles: sesion.roles });
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
