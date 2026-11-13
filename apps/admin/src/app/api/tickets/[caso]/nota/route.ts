// `POST /api/tickets/{caso}/nota` — el operador deja una nota interna en el ticket.
// Operacion decide la regla (403/409/422); aqui solo se exige sesion y la forma del cuerpo.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { validarNota } from "@/lib/cuerpos-admin";
import { ejecutarPost } from "@/lib/ruta-admin";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  return ejecutarPost(peticion, validarNota, (token, valor) => origenDeDatos().notaInternaCaso(token, caso, valor));
}
