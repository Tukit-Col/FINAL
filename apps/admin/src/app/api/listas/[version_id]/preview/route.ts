// `POST /api/listas/{version_id}/preview` — región 4 del revisor: armar la vista
// previa de los tres kits que saldrían de una versión curada.
//
// El administrador, parado sobre una versión, pide previsualizar sin crear un
// trabajo de acudiente: `previewDeVersion` arma un trabajo de preview para ese
// (colegio, grado) y devuelve su `trabajo_id`. La pantalla lo lee luego con el
// `trabajoAdmin(trabajo_id)` de siempre. Preview NO aprueba: `cerrarLista` sigue
// siendo el único que publica.
//
// El destino (colegio, grado, año) llega en el cuerpo: es lo que la revisión ya
// tenía en la pantalla, y así el origen recibe el destino ya resuelto en `ctx`
// sin volver a leer la versión. Las guardas de dominio (404 version_no_existe)
// las impone el backend; aquí solo se traduce el error tal cual (§11).

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
