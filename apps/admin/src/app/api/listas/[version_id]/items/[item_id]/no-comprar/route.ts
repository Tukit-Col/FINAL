// `POST /api/listas/{version_id}/items/{item_id}/no-comprar` — "es el mismo".
//
// El renglon repite a otro: queda en la lista como "no se compra · ya va en la
// linea N" y la lista se vuelve a publicar (version nueva), lo que rearma los
// kits del grado. Cuerpo `{repite_a}`. Devuelve `{version_id}` de la nueva.

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
