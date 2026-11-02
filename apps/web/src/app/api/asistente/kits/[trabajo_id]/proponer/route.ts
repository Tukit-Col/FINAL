// `POST /api/asistente/kits/{trabajo_id}/proponer`: un pedido sobre un kit
// publicado -> propuestas de cambio. Nunca aplica: aplicar es una accion del
// acudiente por la ruta de siempre (`PUT .../lineas/{item}/producto`).

import { ErrorTukit } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { NO_DISPONIBLE, especSegura, reenviar } from "@/components/asistente/servidor";

export const dynamic = "force-dynamic";

const PERFILES = ["Ahorrador", "Fan", "A tu Medida", "Premium"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  let cuerpo: { texto?: unknown; perfil?: unknown } = {};
  try {
    cuerpo = (await peticion.json()) as typeof cuerpo;
  } catch {
    /* validado abajo */
  }
  const { texto, perfil } = cuerpo;
  if (
    !UUID.test(trabajo_id) ||
    typeof texto !== "string" ||
    !texto.trim() ||
    texto.length > 4000 ||
    typeof perfil !== "string" ||
    !PERFILES.includes(perfil)
  ) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "Cuéntanos qué quieres cambiar de tu kit."));
  }

  const { estado, cuerpo: respuesta } = await reenviar(`/v1/kits/${trabajo_id}/asistente/proponer`, {
    texto,
    perfil,
  });
  if (estado !== 200 || respuesta["estado"] !== "propuesta") {
    return Response.json(respuesta, { status: estado });
  }
  const ui = especSegura(respuesta["ui"]);
  if (!ui) return Response.json(NO_DISPONIBLE.cuerpo, { status: NO_DISPONIBLE.estado });
  return Response.json({ ...respuesta, ui });
}
