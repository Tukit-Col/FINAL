// `POST /api/logistica/{pedido}/reconciliar` — consulta a Wompi el pago de un pedido atascado.
// Sin cuerpo: el servicio aplica lo que Wompi diga con el aplicador idempotente del webhook.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ pedido: string }> },
): Promise<Response> {
  const { pedido } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."));
  }
  try {
    return Response.json(await origenDeDatos().reconciliarPagoPedido(token, pedido));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
