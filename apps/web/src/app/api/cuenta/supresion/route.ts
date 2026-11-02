// `POST /api/cuenta/supresion`: el titular borra sus datos (Ley 1581, art. 8).
// Identidad exige la frase escrita, anonimiza, revoca la sesion y responde que
// se borro y que se conserva (con su fundamento). Si salio bien, aqui se borra
// tambien la cookie: el token ya no vale y no tiene sentido dejarlo.
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let confirmacion = "";
  try {
    const cuerpo = (await peticion.json()) as { confirmacion?: unknown };
    if (typeof cuerpo.confirmacion === "string") confirmacion = cuerpo.confirmacion;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer la confirmación."),
    );
  }
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para borrar tus datos."),
    );
  }
  try {
    const resultado = await origenDeDatos().suprimirMisDatos(token, confirmacion);
    const respuesta = NextResponse.json(resultado);
    respuesta.cookies.delete(COOKIE_SESION);
    return respuesta;
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
