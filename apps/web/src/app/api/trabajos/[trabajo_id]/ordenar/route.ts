// `POST /api/trabajos/{id}/ordenar` — el checkout del acudiente.
//
// El navegador manda perfil + correo + dirección; el backend (Inteligencia)
// arma la orden en Comercio server-to-server y devuelve la url de la pasarela.
// Misma costura de siempre: el navegador no toca el backend, el origen (real o
// simulado) se resuelve aquí. Ningún id de producto viaja por esta ruta.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { SolicitudCheckout } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  let cuerpo: SolicitudCheckout;
  try {
    cuerpo = (await peticion.json()) as SolicitudCheckout;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del pago."),
    );
  }

  try {
    const checkout = await origenDeDatos().iniciarCheckout(trabajo_id, cuerpo);
    return Response.json(checkout, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
