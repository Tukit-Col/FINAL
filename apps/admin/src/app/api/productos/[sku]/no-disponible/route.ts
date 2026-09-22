// `POST /api/productos/{sku}/no-disponible` — AD-05.
//
// El efecto no es de este trabajo sino del catalogo: apagar la oferta la
// apaga para todos los trabajos en cola. Por eso la ruta cuelga de
// `/productos` y no de `/trabajos/{id}`.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { MarcarNoDisponible } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ sku: string }> },
): Promise<Response> {
  const { sku } = await contexto.params;

  let cuerpo: MarcarNoDisponible | null;
  try {
    cuerpo = await cuerpoJson<MarcarNoDisponible>(peticion);
  } catch {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer el motivo."));
  }

  try {
    await origenDeDatos().marcarNoDisponible(sku, cuerpo ?? { motivo: "" });
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
