// `POST /api/catalogo/propuestas/{id}/rechazar` — cierra una propuesta de la
// cola descartándola (P4c bis).
//
// El origen delega en la ruta ya existente del backend
// (`POST /v1/admin/propuestas/{id}/rechazar`): no se estrena ruta en catálogo,
// solo se expone por la SPA. `motivo` queda en la traza; `no_surtir` manda el
// concepto a 'no_comprar' en vez de solo descartar el candidato. El cuerpo es
// opcional (un rechazo sin motivo es válido).

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { RechazarPropuesta } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await contexto.params;

  let cuerpo: RechazarPropuesta | null;
  try {
    cuerpo = await cuerpoJson<RechazarPropuesta>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el motivo del rechazo."),
    );
  }

  try {
    const resultado = await origenDeDatos().rechazarPropuesta(id, cuerpo ?? {});
    return Response.json(resultado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
