// `GET /api/listas/{version_id}/documento` — P4, region 1 del revisor.
//
// El PDF crudo de una version importada, servido por esta app para que el
// `<iframe>` de la pantalla lo pida a un origen propio y la URL del backend
// nunca llegue al navegador. `documento()` devuelve el PDF (Blob en el cliente
// HTTP, o el tipo asumido `Blob | ArrayBuffer | string` en el contrato); aqui
// se normaliza a un cuerpo de `Response` con el tipo correcto.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;

  try {
    const documento = await origenDeDatos().documento(version_id);
    // El PDF se muestra embebido, no se descarga: `inline`. Un 404 de
    // `sin_evidencia` sube por `respuestaDeError` como el resto.
    const cabeceras = {
      "Content-Type": "application/pdf",
      "Content-Disposition": "inline",
      "Cache-Control": "no-store",
    };
    const cuerpo =
      typeof documento === "string" || documento instanceof ArrayBuffer
        ? documento
        : // Blob: `Response` lo acepta directo como cuerpo.
          documento;
    return new Response(cuerpo as BodyInit, { headers: cabeceras });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
