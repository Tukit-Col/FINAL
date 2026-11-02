// `POST /api/logistica/{pedido}/avanzar` — el operador mueve un pedido un paso.
//
// El token de la cookie httpOnly se reenvia como Bearer: comercio valida la
// sesion y el rol (operador/admin) y decide si la transicion procede. Aqui no
// se reimplementa esa regla; solo se exige que haya sesion y un JSON legible.
// La cookie es `sameSite=lax`, asi que otro sitio no puede disparar este POST
// con ella.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { SolicitudAvanceAdmin } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ pedido: string }> },
): Promise<Response> {
  const { pedido } = await contexto.params;

  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."),
    );
  }

  let cuerpo: SolicitudAvanceAdmin | null;
  try {
    cuerpo = await cuerpoJson<SolicitudAvanceAdmin>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el avance del pedido."),
    );
  }
  if (!cuerpo?.destino) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el estado destino.", { campo: "destino" }),
    );
  }

  try {
    return Response.json(await origenDeDatos().avanzarPedidoAdmin(token, pedido, cuerpo));
  } catch (causa) {
    // 409/422 suben tal cual, con su `campo`: el formulario marca la entrada.
    return respuestaDeError(causa);
  }
}
