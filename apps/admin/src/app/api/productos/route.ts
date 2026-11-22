import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AltaProducto } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AltaProducto | null;
  try {
    cuerpo = await cuerpoJson<AltaProducto>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del producto."),
    );
  }
  if (!cuerpo) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "Falta el cuerpo con los datos del producto."),
    );
  }

  if (typeof cuerpo.precio !== "number" || !Number.isInteger(cuerpo.precio)) {
    return respuestaDeError(
      new ErrorTukit(
        400,
        "precio_invalido",
        "El precio va en pesos enteros: sin decimales, sin puntos y sin comas.",
        { campo: "precio" },
      ),
    );
  }

  try {
    const alta = await origenDeDatos().altaProducto(cuerpo);
    return Response.json(alta, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
