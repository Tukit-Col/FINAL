import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AltaUtil } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AltaUtil | null;
  try {
    cuerpo = await cuerpoJson<AltaUtil>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del útil."),
    );
  }

  if (!cuerpo?.concepto?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "concepto_invalido", "Hay que elegir un concepto.", {
        campo: "concepto",
      }),
    );
  }
  if (!cuerpo.slug?.trim() || !cuerpo.sku?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "candidato_invalido", "Hay que elegir un candidato de la tienda.", {
        campo: "sku",
      }),
    );
  }

  try {
    const encolada = await origenDeDatos().altaUtil({
      concepto: cuerpo.concepto.trim(),
      slug: cuerpo.slug.trim(),
      sku: cuerpo.sku.trim(),
      consulta: cuerpo.consulta ?? "",
      nivel: cuerpo.nivel ?? "confiable",
    });
    return Response.json(encolada, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
