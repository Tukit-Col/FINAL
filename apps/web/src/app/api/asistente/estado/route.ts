// `GET /api/asistente/estado`: si el asistente esta encendido en este entorno.
// No llama al modelo ni lleva datos del hogar; el panel lo usa para no ofrecer
// sugerencias que no van a funcionar.

import { estadoDelAsistente } from "@/components/asistente/servidor";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return Response.json({ estado: await estadoDelAsistente() });
}
