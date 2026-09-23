// `PATCH /api/colegios/{colegio}` — P4/P1b, edición del perfil de un colegio.
//
// El administrador reescribe la identidad/marca del colegio (logo, sitio web,
// contactos de la secretaría académica). El cuerpo es un `ColegioEditable` con
// solo lo que cambió; `null` limpia un campo. NO edita `nombre` ni `sedes`. La
// respuesta es el `ColegioDetalle` ya actualizado, para que el formulario
// re-pinte sin una segunda lectura. Los contactos son del colegio, nunca de un
// menor (§12.4). Las guardas las impone el backend; aquí solo se traduce el
// error tal cual (§11), sin devolver lo que el cliente mandó.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ColegioEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PATCH(
  peticion: Request,
  contexto: { params: Promise<{ colegio: string }> },
): Promise<Response> {
  const { colegio } = await contexto.params;

  let cuerpo: ColegioEditable | null;
  try {
    cuerpo = await cuerpoJson<ColegioEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los cambios del colegio."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los cambios del colegio."),
    );
  }

  try {
    const actualizado = await origenDeDatos().editarColegio(colegio, cuerpo);
    return Response.json(actualizado, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
