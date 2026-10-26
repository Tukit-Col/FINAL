// `GET /api/trabajos/{id}` — el sondeo del §4.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";
import { consultarTrabajoDelPortador } from "@/lib/sondeo";

export const dynamic = "force-dynamic";

export async function GET(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  try {
    // Con el Bearer de la cookie, como las demas rutas: asi el limite por
    // cuenta lo cuenta y la pantalla de espera puede mostrar su aviso (429).
    const trabajo = await consultarTrabajoDelPortador(
      origenDeDatos(),
      trabajo_id,
      await tokenDeSesion(),
    );
    return Response.json(trabajo, {
      // Un estado que cambia cada pocos segundos no se puede cachear ni un
      // segundo: seria decirle al acudiente que sigue esperando cuando ya
      // termino.
      headers: { "Cache-Control": "no-store" },
    });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
