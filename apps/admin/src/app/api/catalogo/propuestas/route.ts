import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function GET(peticion: Request): Promise<Response> {
  const params = new URL(peticion.url).searchParams;
  const concepto = params.get("concepto") ?? undefined;

  try {
    const propuestas = await origenDeDatos().colaPropuestas(concepto);
    return Response.json(propuestas, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
