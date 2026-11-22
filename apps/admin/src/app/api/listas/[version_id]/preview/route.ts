import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

interface CuerpoPreview {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
}

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;

  let cuerpo: CuerpoPreview | null;
  try {
    cuerpo = await cuerpoJson<CuerpoPreview>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el destino de la vista previa."),
    );
  }
  if (!cuerpo || !cuerpo.colegio_id || !cuerpo.grado || typeof cuerpo.anio_lectivo !== "number") {
    return respuestaDeError(
      new ErrorTukit(
        400,
        "peticion_invalida",
        "Falta el (colegio, grado, año) para armar la vista previa.",
      ),
    );
  }

  try {
    const creado = await origenDeDatos().previewDeVersion(version_id, {
      colegioId: cuerpo.colegio_id,
      grado: cuerpo.grado,
      anioLectivo: cuerpo.anio_lectivo,
    });
    return Response.json(creado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
