import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ItemListaEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;

  let cuerpo: ItemListaEditable | null;
  try {
    cuerpo = await cuerpoJson<ItemListaEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el ítem nuevo."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo del ítem nuevo."),
    );
  }

  try {
    const creado = await origenDeDatos().agregarItemLista(version_id, cuerpo);
    return Response.json(creado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
