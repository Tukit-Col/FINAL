import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

const SIN_SESION = new ErrorTukit(401, "sin_sesion", "Inicia sesión para ver tus casos.");

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ caso_id: string }> },
): Promise<Response> {
  const { caso_id } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) return respuestaDeError(SIN_SESION);
  try {
    return Response.json(await origenDeDatos().miCaso(token, caso_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso_id: string }> },
): Promise<Response> {
  const { caso_id } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) return respuestaDeError(SIN_SESION);
  let texto = "";
  try {
    const cuerpo = (await peticion.json()) as { texto?: unknown };
    if (typeof cuerpo.texto === "string") texto = cuerpo.texto.trim();
  } catch {
    texto = "";
  }
  if (!texto) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "Escribe tu mensaje."));
  }
  try {
    await origenDeDatos().comentarMiCaso(token, caso_id, texto.slice(0, 1000));
    return Response.json({ ok: true }, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
