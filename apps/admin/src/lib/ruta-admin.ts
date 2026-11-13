// Andamiaje comun de las rutas proxy de escritura: sesion, JSON legible, forma
// del cuerpo y llamada al origen. El token sale de la cookie httpOnly y viaja
// como Bearer; las reglas de negocio las decide el servicio.

import { ErrorTukit } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";
import type { Validado } from "@/lib/cuerpos-admin";

export async function ejecutarPost<T, R>(
  peticion: Request,
  validar: (cuerpo: unknown) => Validado<T>,
  llamar: (token: string, valor: T) => Promise<R>,
): Promise<Response> {
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."));
  }
  let cuerpo: unknown;
  try {
    cuerpo = await cuerpoJson<unknown>(peticion);
  } catch {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", "No pudimos leer la petición."));
  }
  const v = validar(cuerpo);
  if (!v.ok) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", v.mensaje, { campo: v.campo }));
  }
  try {
    return Response.json(await llamar(token, v.valor));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
