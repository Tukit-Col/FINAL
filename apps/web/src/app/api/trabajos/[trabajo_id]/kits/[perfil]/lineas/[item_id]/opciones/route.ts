// `GET /api/trabajos/{id}/kits/{perfil}/lineas/{item_id}/opciones` — los
// productos del mismo concepto para el carrusel de "cambiar por otra opción",
// con lo que cambiaría el total.

import { origenDeDatos } from "@tukit/contrato/servidor";
import type { PerfilKit } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";

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
      await origenDeDatos().opcionesDeLinea(trabajo_id, perfil as PerfilKit, item_id),
    );
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
