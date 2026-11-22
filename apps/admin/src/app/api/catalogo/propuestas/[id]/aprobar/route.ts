import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AprobarPropuesta } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await contexto.params;

  let cuerpo: AprobarPropuesta | null;
  try {
    cuerpo = await cuerpoJson<AprobarPropuesta>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el nivel."),
    );
  }
  if (!cuerpo?.nivel?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "nivel_invalido", "Hay que elegir un nivel al aprobar.", {
        campo: "nivel",
      }),
    );
  }

  try {
    const resultado = await origenDeDatos().aprobarPropuesta(id, { nivel: cuerpo.nivel.trim() });
    return Response.json(resultado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
