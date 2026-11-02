// `POST /api/pedidos/{pedido_id}/retracto` — el acudiente ejerce el derecho de
// retracto de UNO de sus pedidos (Ley 1480 de 2011, art. 47).
//
// Exige sesión. Comercio verifica que el pedido sea suyo (403 si es ajeno) y que
// el plazo de 5 días hábiles desde la entrega siga abierto (409 si venció).

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
    // El motivo es opcional: sin cuerpo se registra vacío.
  }
  try {
    return Response.json(await origenDeDatos().retractarPedido(token, pedido_id, motivo), {
      status: 201,
    });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
