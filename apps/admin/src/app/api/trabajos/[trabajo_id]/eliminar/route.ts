// `POST /api/trabajos/{id}/eliminar` — borra un trabajo desechable.
//
// Existe para limpiar los previews que se acumulaban al previsualizar una
// lista varias veces, y cualquier trabajo que ensucie la cola. Un `publicado`
// esta protegido: el backend responde 409 y ese error sube tal cual para que
// la pantalla diga "no se puede, es el kit canonico" y no "algo salio mal".
//
// Es POST y no DELETE porque el navegador solo manda POST a los Route Handlers
// (ver `enviar` en api-navegador.ts); el handler traduce a la llamada DELETE
// del backend por medio de `origenDeDatos().eliminarTrabajo`.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  try {
    await origenDeDatos().eliminarTrabajo(trabajo_id);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
