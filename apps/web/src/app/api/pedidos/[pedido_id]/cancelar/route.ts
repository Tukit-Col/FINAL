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
  let sesion: Awaited<ReturnType<typeof sesionActual>>;
  try {
    sesion = await sesionActual();
  } catch (causa) {
    return respuestaDeError(causa);
  }
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
