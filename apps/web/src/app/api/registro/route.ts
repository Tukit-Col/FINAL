// `POST /api/registro`: alta del acudiente y sus hijos (camino "soy nuevo").
//
// Mismo motivo que `/api/sesion` y `/api/trabajos`: el navegador no habla con
// el backend. Aqui la peticion va al backend real (gateway→identidad).
//
// Tras un alta exitosa INICIA SESION y pone la cookie httpOnly igual que
// `/api/sesion`, para que el padre quede logueado sin pasar por `/ingresar`. La
// clave llega en el body una sola vez y nunca vuelve al cliente; el token va SOLO
// en la cookie, jamas en el cuerpo ni en logs. Si el login falla despues del alta
// (p. ej. el correo ya existia con OTRA clave → 401 de identidad), el registro NO
// se anula: se devuelve `resultado` sin cookie y el padre entra luego por
// `/ingresar`. Asi esta ruta publica nunca abre una cuenta ajena con otra clave.

import { NextResponse } from "next/server";
import { origenDeDatos, type RegistroAcudiente } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let datos: RegistroAcudiente;
  try {
    datos = (await peticion.json()) as RegistroAcudiente;
  } catch {
    return NextResponse.json(
      { error: "peticion_invalida", mensaje: "No pudimos leer los datos del registro." },
      { status: 400 },
    );
  }

  try {
    const resultado = await origenDeDatos().registrarAcudiente(datos);
    // La respuesta al cliente sigue siendo `resultado` ({ usuario_id, creado }):
    // ni la clave ni el token salen nunca en el cuerpo.
    const respuesta = NextResponse.json(resultado);
    try {
      // Inicia sesion con la MISMA credencial del alta y pone la cookie tal cual
      // `/api/sesion` (misma constante y mismas opciones). En `api`, identidad
      // valida la clave: si el correo ya existia con otra, esto da 401 y caemos al
      // catch de abajo sin cookie (no hay toma de cuenta).
      const { token } = await origenDeDatos().iniciarSesion({
        correo: datos.correo,
        clave: datos.clave,
      });
      respuesta.cookies.set(COOKIE_SESION, token, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 8,
      });
    } catch {
      // El alta ya fue exitosa; un login fallido no la invalida. Devolvemos
      // `resultado` sin cookie y el padre podra entrar luego por `/ingresar`.
    }
    return respuesta;
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
