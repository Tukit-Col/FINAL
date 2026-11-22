import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ tarea_id: string }> },
): Promise<Response> {
  const { tarea_id } = await contexto.params;
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para cancelar una solicitud."),
    );
  }
  try {
    return Response.json(await origenDeDatos().cancelarListaSubida(token, tarea_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
