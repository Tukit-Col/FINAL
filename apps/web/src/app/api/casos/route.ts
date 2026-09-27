// `POST /api/casos` — abrir una PQRS desde el centro de ayuda.
//
// La mitad de servidor de la escritura de `operacion`. Igual que `/api/sesion`
// y `/api/trabajos`: el navegador no habla con el backend, y este es el único
// punto donde se habla con el backend real (`/v1/operacion/casos` vía gateway).
// El acudiente no necesita sesión para abrir un caso —igual que no la necesita
// para armar un kit—, así que no se exige cookie aquí.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { SolicitudCaso } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let solicitud: SolicitudCaso;
  try {
    solicitud = (await peticion.json()) as SolicitudCaso;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer tu solicitud."),
    );
  }

  try {
    const creado = await origenDeDatos().crearCaso(solicitud);
    return Response.json(creado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
