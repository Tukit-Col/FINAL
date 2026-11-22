import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ProductoEditable } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError, SIN_CONTENIDO } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function PATCH(
  peticion: Request,
  contexto: { params: Promise<{ sku: string }> },
): Promise<Response> {
  const { sku } = await contexto.params;

  let cuerpo: ProductoEditable | null;
  try {
    cuerpo = await cuerpoJson<ProductoEditable>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los cambios del producto."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los cambios del producto."),
    );
  }

  try {
    const producto = await origenDeDatos().editarProducto(sku, cuerpo);
    return Response.json(producto, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function DELETE(
  _peticion: Request,
  contexto: { params: Promise<{ sku: string }> },
): Promise<Response> {
  const { sku } = await contexto.params;
  try {
    await origenDeDatos().eliminarProducto(sku);
    return SIN_CONTENIDO();
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
