import { origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string; item_id: string }> },
): Promise<Response> {
  const { version_id, item_id } = await contexto.params;
  try {
    const cuerpo = await cuerpoJson<{ repite_a: number }>(peticion);
    const nueva = await origenDeDatos().noComprarRepetido(version_id, item_id, Number(cuerpo?.repite_a));
    return Response.json(nueva, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
