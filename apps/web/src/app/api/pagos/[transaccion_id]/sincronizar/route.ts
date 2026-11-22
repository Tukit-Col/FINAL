import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ transaccion_id: string }> },
): Promise<Response> {
  const { transaccion_id } = await contexto.params;
  try {
    const resultado = await origenDeDatos().sincronizarPago(transaccion_id);
    return Response.json(resultado);
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
