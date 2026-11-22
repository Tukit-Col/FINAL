import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AplicarCanonico } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AplicarCanonico;
  try {
    cuerpo = (await peticion.json()) as AplicarCanonico;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del formulario."),
    );
  }

  let sesion: Awaited<ReturnType<typeof sesionActual>>;
  try {
    sesion = await sesionActual();
  } catch (causa) {
    return respuestaDeError(causa);
  }
  const cuerpoConUsuario: AplicarCanonico = { ...cuerpo, usuario_id: sesion?.usuario_id };

  try {
    const aplicado = await origenDeDatos().aplicarCanonico(cuerpoConUsuario, await tokenDeSesion());
    return Response.json(aplicado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
