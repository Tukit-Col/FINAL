// `POST /api/asistente/decision`: deja constancia de si el acudiente acepto,
// rechazo o edito una propuesta. Es solo bitacora; no cambia ningun dato.

import { ErrorTukit } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { reenviar } from "@/components/asistente/servidor";

export const dynamic = "force-dynamic";

const DECISIONES = ["aceptada", "rechazada", "editada"];
const TIPOS = ["restricciones", "cambio", "descarte"];

export async function POST(peticion: Request): Promise<Response> {
  let c: { propuesta_id?: unknown; decision?: unknown; tipo?: unknown } = {};
  try {
    c = (await peticion.json()) as typeof c;
  } catch {
    /* validado abajo */
  }
  if (
    typeof c.propuesta_id !== "string" ||
    !/^[0-9a-f]{32}$/.test(c.propuesta_id) ||
    typeof c.decision !== "string" ||
    !DECISIONES.includes(c.decision) ||
    typeof c.tipo !== "string" ||
    !TIPOS.includes(c.tipo)
  ) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer tu respuesta."));
  }
  const { estado, cuerpo } = await reenviar("/v1/nl2c/decision", {
    propuesta_id: c.propuesta_id,
    decision: c.decision,
    tipo: c.tipo,
  });
  // La bitacora nunca debe estorbar al acudiente.
  return estado === 202 ? Response.json(cuerpo, { status: 202 }) : Response.json({ estado: "omitida" });
}
