// `POST /api/listas/{version_id}/items` — P4, alta de un renglón en la revisión.
//
// El revisor agrega una línea que el modelo no itemizó. El cuerpo es un
// `ItemListaEditable` (en un alta el backend solo exige `texto_original`); la
// respuesta trae el `item_id` que el backend asignó, para que la región 3 pueda
// re-leer. Las guardas de dominio (lista_ya_revisada 409, campo inválido) las
// impone el backend; aquí solo se traduce el error tal cual (§11), sin devolver
// lo que el cliente mandó.

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
