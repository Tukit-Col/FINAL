// `GET /api/catalogo/tiendas/{slug}/buscar` — candidatos para el alta de útil
// (P4c bis).
//
// Envuelve la búsqueda en vivo (VTEX/Shopify) que el backend hace por
// `tiendas.buscar`. El navegador manda `?consulta=&cuantos=`; este handler lo
// traduce a `buscarEnTienda(slug, consulta, cuantos)` contra el origen del
// servidor. Solo lectura externa: NO escribe. Un `slug` fuera de los válidos lo
// rechaza el backend (`tienda_desconocida`); aquí solo se exige que venga la
// consulta.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

function enteroPositivo(valor: string | null): number | undefined {
  if (valor === null) return undefined;
  const n = Number(valor);
  return Number.isInteger(n) && n > 0 ? n : undefined;
}

export async function GET(
  peticion: Request,
  contexto: { params: Promise<{ slug: string }> },
): Promise<Response> {
  const { slug } = await contexto.params;
  const params = new URL(peticion.url).searchParams;

  const consulta = params.get("consulta")?.trim();
  if (!consulta) {
    return respuestaDeError(
      new ErrorTukit(400, "consulta_invalida", "Hay que escribir qué buscar.", {
        campo: "consulta",
      }),
    );
  }

  try {
    const candidatos = await origenDeDatos().buscarEnTienda(
      slug,
      consulta,
      enteroPositivo(params.get("cuantos")),
    );
    return Response.json(candidatos, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
