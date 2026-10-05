// `POST /api/solicitudes/{trabajo_id}/cancelar`: el acudiente cancela una
// solicitud suya. Inteligencia exige que sea del portador y que el kit no se
// haya comprado ni tenga un pago pendiente (ADR 0031).
import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para cancelar una solicitud."),
    );
  }
  try {
    return Response.json(await origenDeDatos().cancelarSolicitud(token, trabajo_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
