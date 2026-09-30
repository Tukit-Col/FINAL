// `POST /api/catalogo/propuestas/libro` — encola un libro por ISBN (P4c bis).
//
// Manual: el personal copia ISBN/título/precio de Buscalibre (que no expone
// búsqueda en vivo). Como el alta de útil, solo encola (`estado: "pendiente"`):
// una persona decide el nivel al aprobar. El precio va en PESOS enteros y > 0;
// se valida aquí además del form y del origen (tres veces a propósito, §1.4).
// Un ISBN inválido lo rechaza el backend (`isbn_invalido`, 422).

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AltaLibro } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AltaLibro | null;
  try {
    cuerpo = await cuerpoJson<AltaLibro>(peticion);
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del libro."),
    );
  }

  if (!cuerpo?.concepto?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "concepto_invalido", "Hay que elegir un concepto.", {
        campo: "concepto",
      }),
    );
  }
  if (!cuerpo.isbn?.trim() || !cuerpo.titulo?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "libro_invalido", "Hay que dar ISBN y título del libro.", {
        campo: "isbn",
      }),
    );
  }
  if (!Number.isInteger(cuerpo.precio) || cuerpo.precio <= 0) {
    return respuestaDeError(
      new ErrorTukit(400, "precio_invalido", "El precio tiene que ser un entero en pesos mayor que 0.", {
        campo: "precio",
      }),
    );
  }

  try {
    const encolada = await origenDeDatos().altaLibro({
      concepto: cuerpo.concepto.trim(),
      isbn: cuerpo.isbn.trim(),
      titulo: cuerpo.titulo.trim(),
      precio: cuerpo.precio,
      slug: cuerpo.slug?.trim() || "panamericana",
      nivel: cuerpo.nivel ?? "confiable",
    });
    return Response.json(encolada, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
