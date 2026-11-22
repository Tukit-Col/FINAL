import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  try {
    await origenDeDatos().eliminarTrabajo(trabajo_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
