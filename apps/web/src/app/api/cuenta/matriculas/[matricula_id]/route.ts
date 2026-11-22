import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

type Contexto = { params: Promise<{ matricula_id: string }> };

async function tokenOError(): Promise<string | Response> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para cambiar a tus hijos."),
    );
  }
  return token;
}

export async function DELETE(_peticion: Request, contexto: Contexto): Promise<Response> {
  const { matricula_id } = await contexto.params;
  const token = await tokenOError();
  if (typeof token !== "string") return token;
  try {
    await origenDeDatos().quitarMatricula(token, matricula_id);
    return new Response(null, { status: 204 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function PUT(peticion: Request, contexto: Contexto): Promise<Response> {
  const { matricula_id } = await contexto.params;
  let cuerpo: { colegio_id?: unknown; grado?: unknown; apodo?: unknown };
  try {
    cuerpo = (await peticion.json()) as typeof cuerpo;
  } catch {
    cuerpo = {};
  }
  if (typeof cuerpo.colegio_id !== "string" || typeof cuerpo.grado !== "string") {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Elige el colegio y el grado nuevos."),
    );
  }
  const token = await tokenOError();
  if (typeof token !== "string") return token;
  try {
    const resultado = await origenDeDatos().cambiarMatricula(token, matricula_id, {
      colegio_id: cuerpo.colegio_id,
      grado: cuerpo.grado,
      ...(typeof cuerpo.apodo === "string" ? { apodo: cuerpo.apodo } : {}),
    });
    return Response.json(resultado);
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
