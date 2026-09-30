// `PATCH /api/catalogo/productos/{sku}` — CRUD de campos y re-etiqueta (P4c).
// `DELETE /api/catalogo/productos/{sku}` — baja suave (activo=False), 204.
//
// El PATCH escribe solo lo que cambió (`ProductoEditable`, todos opcionales) y
// responde con el producto ya actualizado para que el formulario re-pinte sin
// una segunda lectura. Las guardas de dominio (nivel_invalido, unidad_base_
// invalida, empaque_invalido, quality_score_invalido, campo_no_editable) las
// impone el backend; aquí solo se traduce el error tal cual (§11), sin devolver
// lo que el cliente mandó.

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
