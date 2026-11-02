// `POST /api/tickets/{caso}/responder` — el operador responde al acudiente.
//
// El token de la cookie httpOnly se reenvia como Bearer: operacion valida la
// sesion y el rol (operador/admin), guarda la respuesta en la historia del caso
// y encola el aviso al acudiente. Aqui solo se exige sesion y un JSON legible;
// el texto lo valida operacion (vacio, demasiado largo, ticket cerrado).

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."),
    );
  }

  let cuerpo: { texto?: string } | null;
  try {
    cuerpo = await cuerpoJson<{ texto?: string }>(peticion);
  } catch {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer la respuesta."));
  }
  if (typeof cuerpo?.texto !== "string") {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el texto de la respuesta.", { campo: "texto" }),
    );
  }

  try {
    return Response.json(await origenDeDatos().responderCaso(token, caso, cuerpo.texto));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
