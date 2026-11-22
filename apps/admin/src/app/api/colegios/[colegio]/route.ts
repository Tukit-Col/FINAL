import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ColegioEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PATCH(
  peticion: Request,
  contexto: { params: Promise<{ colegio: string }> },
): Promise<Response> {
  const { colegio } = await contexto.params;

  let cuerpo: ColegioEditable | null;
  try {
    cuerpo = await cuerpoJson<ColegioEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los cambios del colegio."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los cambios del colegio."),
    );
  }

  try {
    const actualizado = await origenDeDatos().editarColegio(colegio, cuerpo);
    return Response.json(actualizado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
