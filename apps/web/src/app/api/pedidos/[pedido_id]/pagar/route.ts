import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { decidirAccionPedido } from "@/lib/pagar-pedido";
import { respuestaDeError } from "@/lib/respuesta";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  let sesion: Awaited<ReturnType<typeof sesionActual>>;
  try {
    sesion = await sesionActual();
  } catch (causa) {
    return respuestaDeError(causa);
  }
  const token = await tokenDeSesion();
  if (!sesion || !token) {
    return respuestaDeError(
      new ErrorTukit(401, "sin_sesion", "Inicia sesión para pagar tu pedido."),
    );
  }
  try {
    const origen = origenDeDatos();
    const decision = decidirAccionPedido(
      await origen.misPedidos(token),
      pedido_id,
      "pagar",
      Date.now(),
    );
    if (!decision.ok) {
      return respuestaDeError(new ErrorTukit(decision.estado, decision.error, decision.mensaje));
    }
    const url_redireccion = `${new URL(peticion.url).origin}/pago/resultado`;
    const pago = await origen.iniciarPagoPedido(token, pedido_id, {
      correo_cliente: sesion.correo,
      url_redireccion,
    });
    return Response.json(pago, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
