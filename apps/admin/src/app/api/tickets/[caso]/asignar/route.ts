// `POST /api/tickets/{caso}/asignar` — el operador asigna o suelta el ticket.
// Operacion decide la regla (403/409/422); aqui solo se exige sesion y la forma del cuerpo.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { validarAsignacion } from "@/lib/cuerpos-admin";
import { ejecutarPost } from "@/lib/ruta-admin";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  return ejecutarPost(peticion, validarAsignacion, (token, valor) => origenDeDatos().asignarCaso(token, caso, valor));
}
