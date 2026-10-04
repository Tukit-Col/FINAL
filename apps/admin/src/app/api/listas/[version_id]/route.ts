// `DELETE /api/listas/{version_id}` — saca de la cola una versión sin revisar.
//
// Para las subidas repetidas o equivocadas que ensucian la cola. Se lleva sus
// renglones y el PDF de la importación. Una versión ya revisada es la que ve el
// acudiente: el backend responde 409 `lista_ya_revisada` y ese error sube tal
// cual (§11) para que la pantalla diga por qué no.

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
