// `DELETE /api/listas/{version_id}` — P4, descartar una versión de la cola.
//
// El revisor bota una versión SIN revisar que no va (una sugerencia errada, un
// onboarding equivocado). La guarda la impone el backend: alza 409
// `lista_ya_revisada` si ya se aprobó —una lista oficial no se borra, se corrige
// con una versión nueva—. Aquí solo se traduce el error tal cual (§11). 204 sin
// cuerpo cuando el backend acepta.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function DELETE(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;
  try {
    await origenDeDatos().eliminarVersion(version_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
