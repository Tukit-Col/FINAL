// `POST /api/registro`: alta del acudiente y sus hijos.
//
// Decisiones:
// - El navegador no habla con el backend: la petición va al gateway desde el servidor.
// - Tras un alta exitosa inicia sesión y pone la cookie httpOnly. La clave llega en el cuerpo una sola
//   vez y no vuelve al cliente; el token va solo en la cookie, nunca en el cuerpo ni en los registros.
// - Si el login falla después del alta (por ejemplo, el correo ya existía con otra clave), el registro
//   no se anula: se devuelve `resultado` sin cookie y el padre entra luego por `/ingresar`. Así esta
//   ruta pública nunca abre una cuenta ajena con otra clave.

import { NextResponse } from "next/server";
import { ErrorTukit, origenDeDatos, type RegistroAcudiente } from "@tukit/contrato/servidor";
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
    const respuesta = NextResponse.json(resultado);
    try {
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
    } catch (causa) {
      if (!resultado.creado && causa instanceof ErrorTukit && causa.estado === 401) {
        return NextResponse.json(
          {
            error: "correo_ya_registrado",
            mensaje:
              "Ese correo ya tiene una cuenta en TUKIT. Entra con tu clave (o recupérala) y seguimos con lo que llenaste.",
          },
          { status: 409 },
        );
      }
      if (causa instanceof ErrorTukit && causa.estado === 429) {
        return respuestaDeError(
          new ErrorTukit(429, causa.codigo, causa.message, {
            ...causa.detalle,
            ...resultado,
            cuenta_creada: true,
          }),
        );
      }
    }
    return respuesta;
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
