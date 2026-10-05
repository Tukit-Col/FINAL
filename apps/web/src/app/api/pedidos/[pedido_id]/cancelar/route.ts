// `POST /api/pedidos/{pedido_id}/cancelar` — cancelar desde "Mis pedidos" un
// pedido que quedo pendiente.
//
// Se verifica con la sesion de la cookie que el pedido sea del acudiente y siga
// pendiente (un pedido vencido tambien se cancela: asi libera su reserva).
// Comercio pregunta a Wompi antes de cancelar y responde 409 si hay un pago
// aprobado o en curso; ese mensaje llega tal cual al acudiente.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { decidirAccionPedido } from "@/lib/pagar-pedido";
import { respuestaDeError } from "@/lib/respuesta";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  const sesion = await sesionActual();
  const token = await tokenDeSesion();
  if (!sesion || !token) {
    return respuestaDeError(
      new ErrorTukit(401, "sin_sesion", "Inicia sesión para cancelar tu pedido."),
    );
  }
  try {
    const origen = origenDeDatos();
    const decision = decidirAccionPedido(
      await origen.misPedidos(token),
      pedido_id,
      "cancelar",
      Date.now(),
    );
    if (!decision.ok) {
      return respuestaDeError(new ErrorTukit(decision.estado, decision.error, decision.mensaje));
    }
    return Response.json(await origen.cancelarPedido(token, pedido_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
