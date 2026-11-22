import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(): Promise<Response> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para revocar tu autorización."),
    );
  }
  try {
    return Response.json(await origenDeDatos().revocarConsentimientos(token));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
