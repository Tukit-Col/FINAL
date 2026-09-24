// `POST /api/catalogo/propuestas/util-manual` — encola un útil a mano (P4c bis).
//
// Para lo que la búsqueda en vivo no encuentra (VTEX/Shopify no lo indexa, o es
// una tienda sin búsqueda): el personal escribe nombre, precio, tienda y —si lo
// tiene— SKU y marca. Como el resto de altas, solo encola (`estado: "pendiente"`):
// una persona decide el nivel al aprobar. El precio va en PESOS enteros y > 0;
// se valida aquí además del form y del origen (tres veces a propósito, §1.4). La
// tienda tiene que existir en la BD; si no, el backend responde `tienda_desconocida`.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AltaUtilManual } from "@tukit/contrato";
import { cuerpoJson, respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AltaUtilManual | null;
  try {
    cuerpo = await cuerpoJson<AltaUtilManual>(peticion);
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
  if (!cuerpo.nombre?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "nombre_invalido", "El útil necesita un nombre.", {
        campo: "nombre",
      }),
    );
  }
  if (!cuerpo.slug?.trim()) {
    return respuestaDeError(
      new ErrorTukit(400, "tienda_invalida", "Hay que elegir o escribir una tienda.", {
        campo: "slug",
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
    const encolada = await origenDeDatos().altaUtilManual({
      concepto: cuerpo.concepto.trim(),
      nombre: cuerpo.nombre.trim(),
      precio: cuerpo.precio,
      slug: cuerpo.slug.trim(),
      sku: cuerpo.sku?.trim() || undefined,
      url: cuerpo.url?.trim() || undefined,
      marca: cuerpo.marca?.trim() || undefined,
      nivel: cuerpo.nivel ?? "confiable",
    });
    return Response.json(encolada, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
