// `POST /api/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` — AD-04.
//
// Fija el producto de UN kit (por-nivel). Route Handler por la misma razon que
// `validar`: la URL del backend y la bandera de origen se quedan en el
// servidor, y el borde habla el `{error, mensaje}` del §11. El navegador manda
// POST; el origen traduce a la ruta PUT de inteligencia.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string; perfil: string; item_id: string }> },
): Promise<Response> {
  const { trabajo_id, perfil, item_id } = await contexto.params;

  let cuerpo: { sku?: string } | null;
  try {
    cuerpo = await cuerpoJson<{ sku?: string }>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el producto elegido."),
    );
  }
  if (!cuerpo?.sku) {
    return respuestaDeError(
      new ErrorTukit(400, "sku_requerido", "Falta el sku del producto a fijar."),
    );
  }

  try {
    await origenDeDatos().fijarProductoLinea(trabajo_id, perfil, item_id, cuerpo.sku);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
