// `POST /api/pedidos/{pedido_id}/pagar` — pagar desde "Mis pedidos" un pedido
// que quedo pendiente (el acudiente cerro Wompi o le rechazaron el pago).
//
// No re-arma la orden: Comercio crea un intento de pago nuevo sobre el mismo
// pedido, con su precio congelado. Antes se verifica, con la sesion de la
// cookie, que el pedido sea del acudiente y siga pendiente; el correo del
// comprobante sale de la sesion, sin formulario.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { decidirPagoPedido } from "@/lib/pagar-pedido";
import { respuestaDeError } from "@/lib/respuesta";
import { sesionActual } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  const sesion = await sesionActual();
  if (!sesion) {
    return respuestaDeError(
      new ErrorTukit(401, "sin_sesion", "Inicia sesión para pagar tu pedido."),
    );
  }
  try {
    const origen = origenDeDatos();
    const decision = decidirPagoPedido(await origen.misPedidos(sesion.usuario_id), pedido_id);
    if (!decision.ok) {
      return respuestaDeError(new ErrorTukit(decision.estado, decision.error, decision.mensaje));
    }
    // PSE se lleva la pestana al banco y vuelve por aqui con `?id=`.
    const url_redireccion = `${new URL(peticion.url).origin}/pago/resultado`;
    const pago = await origen.iniciarPagoPedido(pedido_id, {
      correo_cliente: sesion.correo,
      url_redireccion,
    });
    return Response.json(pago, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
