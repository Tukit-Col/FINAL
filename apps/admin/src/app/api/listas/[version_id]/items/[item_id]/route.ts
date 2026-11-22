import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ItemListaEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PATCH(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string; item_id: string }> },
): Promise<Response> {
  const { version_id, item_id } = await contexto.params;

  let cuerpo: ItemListaEditable | null;
  try {
    cuerpo = await cuerpoJson<ItemListaEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los cambios del ítem."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los cambios del ítem."),
    );
  }

  try {
    await origenDeDatos().editarItemLista(version_id, item_id, cuerpo);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function DELETE(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string; item_id: string }> },
): Promise<Response> {
  const { version_id, item_id } = await contexto.params;
  try {
    await origenDeDatos().quitarItemLista(version_id, item_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
