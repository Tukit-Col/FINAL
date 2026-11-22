import { estadoDelAsistente } from "@/components/asistente/servidor";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return Response.json({ estado: await estadoDelAsistente() });
}
