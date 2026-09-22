// `POST /api/trabajos/{id}/revision` — AD-06, el unico cuerpo que el §7 fija.
//
// Aprobar publica y dispara la notificacion al acudiente; devolver reabre el
// trabajo sin avisarle. Es la accion irreversible de la consola, asi que un
// `decision` que no sea uno de los dos no se interpreta: se rechaza.

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
    // Un 409 `trabajo_ya_publicado` sube tal cual: la pantalla tiene que
    // decir "ya se publico" y no "algo salio mal".
    return respuestaDeError(causa);
  }
}
