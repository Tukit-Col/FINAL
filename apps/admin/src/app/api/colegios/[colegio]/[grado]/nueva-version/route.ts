import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ colegio: string; grado: string }> },
): Promise<Response> {
  const { colegio, grado } = await contexto.params;

  let cuerpo: { anio_lectivo?: number } | null;
  try {
    cuerpo = await cuerpoJson<{ anio_lectivo?: number }>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el año lectivo."),
    );
  }
  const anio = cuerpo?.anio_lectivo;
  if (typeof anio !== "number" || !Number.isInteger(anio)) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el año lectivo de la lista."),
    );
  }

  try {
    const creada = await origenDeDatos().nuevaVersion(colegio, grado, anio);
    return Response.json(creada, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
