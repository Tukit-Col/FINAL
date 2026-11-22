import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";
import { consultarTrabajoDelPortador } from "@/lib/sondeo";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  try {
    const trabajo = await consultarTrabajoDelPortador(
      origenDeDatos(),
      trabajo_id,
      await tokenDeSesion(),
    );
    return Response.json(trabajo, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
