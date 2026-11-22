import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { PerfilKit } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function PUT(
  peticion: Request,
  contexto: {
    params: Promise<{ trabajo_id: string; perfil: string; item_id: string }>;
  },
): Promise<Response> {
  const { trabajo_id, perfil, item_id } = await contexto.params;
  let descartado: unknown;
  try {
    descartado = ((await peticion.json()) as { descartado?: unknown }).descartado;
  } catch {
    descartado = undefined;
  }
  if (typeof descartado !== "boolean") {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta decir si quieres quitar o volver a poner el producto."),
    );
  }

  try {
    const cambio = await origenDeDatos().descartarLineaDeKit(
      trabajo_id,
      perfil as PerfilKit,
      item_id,
      descartado,
      await tokenDeSesion(),
    );
    return Response.json(cambio);
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
