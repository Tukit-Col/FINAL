// `POST /api/catalogo/propuestas/util` — encola un útil elegido (P4c bis).
//
// Encolar y aprobar son dos pasos separados: esto solo mete la propuesta en la
// cola visible (`estado: "pendiente"`); una persona decide el nivel al aprobar.
// El backend re-busca por `(slug, sku)` para no confiar en un precio que el
// navegador pudo alterar; por eso el cuerpo lleva `consulta`, no el precio. Un
// SKU que ya no está en la tienda, o un concepto inexistente, los rechaza el
// backend (`candidato_no_disponible` / `concepto_no_existe`, 422); aquí solo se
// exige que vengan las claves.

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
