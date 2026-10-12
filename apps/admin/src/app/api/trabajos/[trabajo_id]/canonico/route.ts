// `POST /api/trabajos/{id}/canonico` — aprobar la lista desde su preview, o
// publicar la versión nueva de los kits de una lista ya aprobada.
//
// Un preview no tiene acudiente, así que "publicar y avisar" no aplica. Lo que
// sí tiene sentido es lo que el revisor quiere al mirarlo: aprobar la LISTA del
// colegio (Catálogo) y quedarse con ESTOS tres kits —con los ajustes que hizo—
// como los canónicos del grado (Inteligencia). Desde ahí, el acudiente que pida
// su kit sin tope de gasto lo recibe al instante, sin volver a optimizar.
//
// El orden importa: primero se aprueba la lista (si quedan propuestas sin
// decidir, el Catálogo responde 409 y no se fija nada) y después se fija el
// preview. Aprobar también le pide a Inteligencia que arme el canónico por su
// cuenta; si ese cálculo termina después, ve que la versión ya tiene canónico y
// se retira, así que el preview gana.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;

  let cuerpo: { nota?: string } | null;
  try {
    cuerpo = await cuerpoJson<{ nota?: string }>(peticion);
  } catch {
    cuerpo = null;
  }
  const nota = cuerpo?.nota?.trim() || undefined;

  try {
    const origen = origenDeDatos();
    const trabajo = await origen.trabajoAdmin(trabajo_id);
    // Un borrador de edición (la versión siguiente de kits ya publicados) no
    // aprueba nada en Catálogo: la lista ya está aprobada. Solo se publica y
    // pasa a ser el canónico; Inteligencia rechaza con 409 si mientras tanto
    // otro canónico reemplazó al que se estaba editando.
    if (trabajo.origen === "canonico_lista" && trabajo.hijos?.[0]?.basado_en) {
      await origen.fijarCanonico(trabajo_id, nota ? { nota } : {});
      return SIN_CONTENIDO();
    }
    if (trabajo.origen !== "preview_onboarding") {
      throw new ErrorTukit(
        409,
        "trabajo_con_acudiente",
        "Solo un preview se guarda como kit canónico; el trabajo de un acudiente se publica.",
      );
    }
    const versionId = trabajo.hijos?.[0]?.version_id;
    if (!versionId) {
      throw new ErrorTukit(
        409,
        "preview_sin_version",
        "Este preview es anterior a los kits canónicos y no sabe de qué versión salió. Vuelve a previsualizar la lista y apruébala desde el nuevo.",
      );
    }
    await origen.cerrarLista(versionId);
    await origen.fijarCanonico(trabajo_id, nota ? { nota } : {});
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
