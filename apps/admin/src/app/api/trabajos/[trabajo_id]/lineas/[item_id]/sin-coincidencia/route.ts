import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { SinCoincidencia } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string; item_id: string }> },
): Promise<Response> {
  const { trabajo_id, item_id } = await contexto.params;

  let cuerpo: SinCoincidencia | null;
  try {
    cuerpo = await cuerpoJson<SinCoincidencia>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el motivo."),
    );
  }

  try {
    await origenDeDatos().marcarSinCoincidencia(trabajo_id, item_id, cuerpo ?? { motivo: "" });
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
