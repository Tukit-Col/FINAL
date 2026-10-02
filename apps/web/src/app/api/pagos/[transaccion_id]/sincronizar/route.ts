// `POST /api/pagos/{transaccion_id}/sincronizar` — el regreso de la pasarela.
//
// Al volver de Wompi el navegador solo trae el id de la transacción; el backend
// (Comercio) la consulta a la pasarela y devuelve el estado del pago y del
// pedido. Misma costura de siempre: el origen se resuelve aquí, en el servidor.

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
