// `PATCH /api/listas/{version_id}/colegio` — P4/E4, completar el perfil del
// colegio NUEVO de una versión antes de aprobarla.
//
// Cuando la versión la subió un acudiente de un colegio que aún no existe en
// Tukit, el revisor puede llenar más datos (logo, sitio, dirección, contacto)
// para que la aprobación cree la identidad completa y no solo con nombre y
// grado. El cuerpo es un `ColegioNuevoEditable` (solo los campos presentes; el
// backend hace merge sobre `colegio_datos`); la respuesta trae los datos ya
// combinados. Las guardas (lista_ya_revisada 409, sin_colegio_por_crear 409)
// las impone el backend; aquí solo se traduce el error tal cual (§11).

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
