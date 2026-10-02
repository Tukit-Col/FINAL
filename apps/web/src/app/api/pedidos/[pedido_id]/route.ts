// `GET /api/pedidos/{pedido_id}` — el detalle de un pedido para la pantalla de
// resultado del pago: productos, medio de pago y entrega.
//
// Misma costura de siempre: el navegador no toca el backend, el origen se
// resuelve aquí, en el servidor. El id es el UUID opaco que la sincronización
// del pago le devolvió a este mismo navegador.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  try {
    return Response.json(await origenDeDatos().pedido(pedido_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
