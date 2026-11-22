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
