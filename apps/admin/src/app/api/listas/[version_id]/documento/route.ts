// `GET /api/listas/{version_id}/documento` — P4, region 1 del revisor.
//
// El PDF crudo de una version importada, servido por esta app para que el
// `<iframe>` de la pantalla lo pida a un origen propio y la URL del backend
// nunca llegue al navegador. `documento()` devuelve el PDF (Blob en el cliente
// HTTP, o el tipo asumido `Blob | ArrayBuffer | string` en el contrato); aqui
// se normaliza a un cuerpo de `Response` con el tipo correcto.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ version_id: string }> },
): Promise<Response> {
  const { version_id } = await contexto.params;

  try {
    const documento = await origenDeDatos().documento(version_id);
    // El documento (PDF o imagen) se muestra embebido, no se descarga: `inline`.
    // El tipo real viaja en el Blob (`.type` = Content-Type del backend); se
    // reenvia para que una imagen se sirva como image/* y no como PDF.
    const tipo =
      documento instanceof Blob && documento.type ? documento.type : "application/pdf";
    const cabeceras = {
      "Content-Type": tipo,
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
    // Sin documento: 404 seco, sin volcar el JSON de `sin_evidencia` al iframe.
    if (causa instanceof ErrorTukit && causa.estado === 404) {
      return new Response(null, { status: 404 });
    }
    return respuestaDeError(causa);
  }
}
