import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos, type HijoNuevo } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: { hijos?: HijoNuevo[] };
  try {
    cuerpo = (await peticion.json()) as { hijos?: HijoNuevo[] };
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los hijos a guardar."),
    );
  }

  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para guardar tus hijos."),
    );
  }

  try {
    const resultado = await origenDeDatos().guardarMatriculas(token, cuerpo.hijos ?? []);
    return Response.json(resultado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
