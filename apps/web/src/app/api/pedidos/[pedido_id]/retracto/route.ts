import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ pedido_id: string }> },
): Promise<Response> {
  const { pedido_id } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sin_sesion", "Inicia sesión para pedir el retracto de tu pedido."),
    );
  }
  let motivo = "";
  try {
    const cuerpo = (await peticion.json()) as { motivo?: unknown };
    if (typeof cuerpo.motivo === "string") motivo = cuerpo.motivo.slice(0, 500);
  } catch {
  }
  try {
    return Response.json(await origenDeDatos().retractarPedido(token, pedido_id, motivo), {
      status: 201,
    });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
