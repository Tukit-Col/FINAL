// `GET /api/pedidos/{pedido_id}` — el detalle de un pedido para la pantalla de
// resultado del pago: productos, medio de pago y entrega.
//
// Misma costura de siempre: el navegador no toca el backend, el origen se
// resuelve aquí, en el servidor. El id es el UUID opaco que la sincronización
// del pago le devolvió a este mismo navegador, y comercio solo lo entrega a su
// dueño: viaja el token de la cookie (un pedido ajeno es 404).

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(new ErrorTukit(401, "sin_sesion", "Inicia sesión para ver tu pedido."));
  }
  try {
    return Response.json(await origenDeDatos().miPedido(token, pedido_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
