// `POST /api/listas/{version_id}/avisos/descartar` — "son distintos".
//
// El aviso no aplica y no debe volver a salir. Se guarda en el renglon y no crea
// version: no cambia lo que se compra. Cuerpo `{item_id, clave}`; los errores
// (aviso_invalido 400, item_no_existe 404) son los del backend tal cual.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;
  try {
    const cuerpo = await cuerpoJson<{ item_id: string; clave: string }>(peticion);
    await origenDeDatos().descartarAviso(version_id, cuerpo?.item_id ?? "", cuerpo?.clave ?? "");
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
