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
        :
          documento;
    return new Response(cuerpo as BodyInit, { headers: cabeceras });
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) {
      return new Response(null, { status: 404 });
    }
    return respuestaDeError(causa);
  }
}
