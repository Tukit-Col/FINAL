// `GET /api/logistica/{pedido}/vista-previa?destino=` — lo que verá el acudiente al mover el pedido.
// No escribe nada; comercio arma la línea de tiempo con vistas recortadas.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { validarDestinoDePrevia } from "@/lib/cuerpos-admin";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function GET(
  peticion: Request,
  contexto: { params: Promise<{ pedido: string }> },
): Promise<Response> {
  const { pedido } = await contexto.params;
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."));
  }
  const v = validarDestinoDePrevia(new URL(peticion.url).searchParams.get("destino"));
  if (!v.ok) {
    return respuestaDeError(new ErrorTukit(400, "peticion_invalida", v.mensaje, { campo: v.campo }));
  }
  try {
    return Response.json(await origenDeDatos().vistaPreviaPedido(token, pedido, v.valor));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
