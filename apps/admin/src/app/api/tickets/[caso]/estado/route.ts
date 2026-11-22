import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."),
    );
  }

  let cuerpo: { destino?: string } | null;
  try {
    cuerpo = await cuerpoJson<{ destino?: string }>(peticion);
  } catch {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer el cambio."));
  }
  if (!cuerpo?.destino) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el estado destino.", { campo: "destino" }),
    );
  }

  try {
    return Response.json(await origenDeDatos().cambiarEstadoCaso(token, caso, cuerpo.destino));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
