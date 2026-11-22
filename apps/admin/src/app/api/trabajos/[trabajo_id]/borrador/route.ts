import { NextResponse } from "next/server";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(
  _peticion: Request,
  contexto: { params: Promise<{ trabajo_id: string }> },
): Promise<Response> {
  const { trabajo_id } = await contexto.params;
  try {
    return NextResponse.json(await origenDeDatos().abrirBorradorKits(trabajo_id));
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
