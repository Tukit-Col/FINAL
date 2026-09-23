// `POST /api/trabajos/{id}/lineas/{item_id}/validar` — AD-02.
//
// Route Handler y no Server Action, igual que en `apps/web` y por la misma
// razon: la bandera `TUKIT_ORIGEN_DATOS` y la URL del backend se resuelven en
// un solo sitio de servidor, y el borde queda siendo HTTP con la forma de
// error del §11, que es lo que el backend real va a hablar. Una Server Action
// tambien se ejecutaria en el servidor, pero el error volveria como una
// excepcion serializada en vez de un `{error, mensaje}` con codigo de estado,
// y la pantalla tendria que inventar el mensaje.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ValidarLinea } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string; item_id: string }> },
): Promise<Response> {
  const { trabajo_id, item_id } = await contexto.params;

  let cuerpo: ValidarLinea;
  try {
    // Sin cuerpo se lee como "confirmo el que el sistema eligio", que es lo
    // que el contrato dice de un `ValidarLinea` sin `sku`.
    cuerpo = (await cuerpoJson<ValidarLinea>(peticion)) ?? {};
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos de la validación."),
    );
  }

  try {
    await origenDeDatos().validarLinea(trabajo_id, item_id, cuerpo);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
