import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { RechazarPropuesta } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await contexto.params;

  let cuerpo: RechazarPropuesta | null;
  try {
    cuerpo = await cuerpoJson<RechazarPropuesta>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el motivo del rechazo."),
    );
  }

  try {
    const resultado = await origenDeDatos().rechazarPropuesta(id, cuerpo ?? {});
    return Response.json(resultado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
