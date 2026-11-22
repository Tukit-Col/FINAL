import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function DELETE(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;
  try {
    await origenDeDatos().eliminarVersionLista(version_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
