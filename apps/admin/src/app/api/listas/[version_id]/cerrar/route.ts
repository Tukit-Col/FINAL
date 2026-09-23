// `POST /api/listas/{version_id}/cerrar` — P4, aprobar y publicar la versión.
//
// Cerrar una versión de lista la marca como revisada y deja el par (colegio,
// grado) disponible para los acudientes. No lleva cuerpo: lo único que importa
// es que pasó. Las guardas de dominio (lista_ya_revisada 409, sin_renglones) las
// impone el backend; aquí solo se traduce el error tal cual (§11). 204 sin
// cuerpo cuando el backend cierra la versión.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;
  try {
    await origenDeDatos().cerrarLista(version_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
