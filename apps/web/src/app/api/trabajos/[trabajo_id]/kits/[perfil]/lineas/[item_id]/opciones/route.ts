// `GET /api/trabajos/{id}/kits/{perfil}/lineas/{item_id}/opciones` — los
// productos del mismo concepto para el carrusel de "cambiar por otra opción",
// con lo que cambiaría el total.

import { origenDeDatos } from "@tukit/contrato/servidor";
import type { PerfilKit } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: {
    params: Promise<{ trabajo_id: string; perfil: string; item_id: string }>;
  },
): Promise<Response> {
  const { trabajo_id, perfil, item_id } = await contexto.params;
  try {
    return Response.json(
      // Con el Bearer de la cookie: inteligencia solo entrega las opciones de un
      // kit con dueno a la sesion de ese dueno.
      await origenDeDatos().opcionesDeLinea(
        trabajo_id,
        perfil as PerfilKit,
        item_id,
        await tokenDeSesion(),
      ),
    );
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
