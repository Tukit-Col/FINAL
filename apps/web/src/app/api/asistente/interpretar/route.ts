import { ErrorTukit } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { NO_DISPONIBLE, especSegura, imagenDePersonaje, reenviar } from "@/components/asistente/servidor";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let texto: unknown;
  try {
    texto = ((await peticion.json()) as { texto?: unknown }).texto;
  } catch {
    texto = undefined;
  }
  if (typeof texto !== "string" || !texto.trim() || texto.length > 4000) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "Cuéntanos qué necesitas para el kit."));
  }

  const { estado, cuerpo } = await reenviar("/v1/nl2c/interpretar", { texto });
  if (estado !== 200 || cuerpo["estado"] !== "propuesta") {
    return Response.json(cuerpo, { status: estado });
  }
  const ui = especSegura(cuerpo["ui"]);
  if (!ui) return Response.json(NO_DISPONIBLE.cuerpo, { status: NO_DISPONIBLE.estado });

  for (const c of ui.componentes) {
    if (c.tipo === "TarjetaPersonaje") c.props.imagen_url = await imagenDePersonaje(c.props.nombre);
  }
  return Response.json({ ...cuerpo, ui });
}
