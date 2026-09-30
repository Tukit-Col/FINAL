// `POST /api/catalogo/conceptos` — crea un concepto nuevo (P4c bis).
//
// El otro brazo de la curación: en vez de encolar un producto bajo un concepto
// que ya existe, nace el concepto (el código C0NN lo autogenera el backend) y
// después se le encolan sus niveles con `altaUtil`/`altaLibro`. Así crece la BD
// a medida que se revisa cada lista subida. Un nombre duplicado (409) o faltar
// nombre/categoría (422) los rechaza el backend; aquí solo se exige que vengan.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { CrearConcepto } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: CrearConcepto | null;
  try {
    cuerpo = await cuerpoJson<CrearConcepto>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del concepto."),
    );
  }

  if (!cuerpo?.nombre_canonico?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "nombre_invalido", "El concepto necesita un nombre canónico.", {
        campo: "nombre_canonico",
      }),
    );
  }
  if (!cuerpo.categoria?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "categoria_invalida", "El concepto necesita una categoría.", {
        campo: "categoria",
      }),
    );
  }

  try {
    const creado = await origenDeDatos().crearConcepto({
      nombre_canonico: cuerpo.nombre_canonico.trim(),
      categoria: cuerpo.categoria.trim(),
      sinonimos: cuerpo.sinonimos,
      tipo_item: cuerpo.tipo_item,
      admite_personaje: cuerpo.admite_personaje,
    });
    return Response.json(creado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
