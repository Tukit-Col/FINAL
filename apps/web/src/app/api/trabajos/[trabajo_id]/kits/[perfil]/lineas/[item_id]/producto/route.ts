// `PUT /api/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` — el
// acudiente cambia un producto de su kit por el sugerido o una alternativa.
//
// La sesión viaja desde la cookie httpOnly (el navegador nunca ve el token):
// si el trabajo tiene dueño, Inteligencia exige que sea la suya. Sin cookie se
// manda igual, porque la ruta rápida admite trabajos sin cuenta.

import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { PerfilKit } from "@tukit/contrato";
import { COOKIE_SESION } from "@/lib/sesion";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PUT(
  peticion: Request,
  contexto: {
    params: Promise<{ trabajo_id: string; perfil: string; item_id: string }>;
  },
): Promise<Response> {
  const { trabajo_id, perfil, item_id } = await contexto.params;
  let sku: unknown;
  try {
    sku = ((await peticion.json()) as { sku?: unknown }).sku;
  } catch {
    sku = undefined;
  }
  if (typeof sku !== "string" || !sku) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el producto que quieres elegir."),
    );
  }

  const token = (await cookies()).get(COOKIE_SESION)?.value;
  try {
    const cambio = await origenDeDatos().cambiarProductoDeKit(
      trabajo_id,
      perfil as PerfilKit,
      item_id,
      sku,
      token,
    );
    return Response.json(cambio);
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
