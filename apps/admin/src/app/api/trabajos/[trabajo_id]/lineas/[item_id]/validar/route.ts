import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ValidarLinea } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string; item_id: string }> },
): Promise<Response> {
  const { trabajo_id, item_id } = await contexto.params;

  let cuerpo: ValidarLinea;
  try {
    cuerpo = (await cuerpoJson<ValidarLinea>(peticion)) ?? {};
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos de la validación."),
    );
  }

  try {
    await origenDeDatos().validarLinea(trabajo_id, item_id, cuerpo);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
