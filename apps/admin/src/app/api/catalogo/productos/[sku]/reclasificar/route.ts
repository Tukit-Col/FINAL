import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ReclasificarProducto } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ sku: string }> },
): Promise<Response> {
  const { sku } = await contexto.params;

  let cuerpo: ReclasificarProducto | null;
  try {
    cuerpo = await cuerpoJson<ReclasificarProducto>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el concepto."),
    );
  }
  if (!cuerpo?.concepto?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "concepto_invalido", "Hay que elegir un concepto destino.", {
        campo: "concepto",
      }),
    );
  }

  try {
    const producto = await origenDeDatos().reclasificarProducto(sku, cuerpo.concepto);
    return Response.json(producto, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
