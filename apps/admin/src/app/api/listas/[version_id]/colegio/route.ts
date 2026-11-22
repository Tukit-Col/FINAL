import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ColegioNuevoEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PATCH(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;

  let cuerpo: ColegioNuevoEditable | null;
  try {
    cuerpo = await cuerpoJson<ColegioNuevoEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del colegio."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los datos del colegio."),
    );
  }

  try {
    const datos = await origenDeDatos().completarColegioDeVersion(version_id, cuerpo);
    return Response.json(datos, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
