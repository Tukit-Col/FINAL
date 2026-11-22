import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { DecisionRevision } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;

  let cuerpo: DecisionRevision | null;
  try {
    cuerpo = await cuerpoJson<DecisionRevision>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer la decisión."),
    );
  }

  if (cuerpo?.decision !== "aprobar" && cuerpo?.decision !== "devolver") {
    return respuestaDeError(
      new ErrorTukit(400, "decision_invalida", "La decisión solo puede ser aprobar o devolver.", {
        campo: "decision",
      }),
    );
  }

  try {
    await origenDeDatos().decidirRevision(trabajo_id, cuerpo);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
