// `POST /api/trabajos/{id}/borrador` — editar los kits ya publicados de un grado.
//
// `{id}` es el canónico vigente. No se edita en sitio: el acudiente que ya
// empezó apunta a ese trabajo y debe seguir viendo lo que pagó. Inteligencia lo
// copia a un borrador en revisión (o devuelve el que ya estaba abierto) y la
// página del colegio navega a `/trabajos/{borrador}` para corregirlo; publicarlo
// es `POST /api/trabajos/{borrador}/canonico`.

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
