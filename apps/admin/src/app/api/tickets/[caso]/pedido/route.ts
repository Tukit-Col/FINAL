// `POST /api/tickets/{caso}/pedido` — vincula el ticket a un pedido.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."),
    );
  }

  let cuerpo: { pedido_id?: string } | null;
  try {
    cuerpo = await cuerpoJson<{ pedido_id?: string }>(peticion);
  } catch {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer el vínculo."));
  }
  if (!cuerpo?.pedido_id) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el pedido.", { campo: "pedido_id" }),
    );
  }

  try {
    return Response.json(await origenDeDatos().vincularPedidoCaso(token, caso, cuerpo.pedido_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
