// `GET /api/direccion/buscar?q=...` — busca una dirección en OpenStreetMap
// (Nominatim) para el checkout cuando no hay llave de Google (ADR 0049).
//
// El navegador nunca habla con Nominatim: la política del servicio público pide
// un User-Agent con contacto, una petición por segundo en total y caché, y eso
// solo se cumple de forma global desde el servidor. El contacto sale de
// `TUKIT_NOMINATIM_CONTACTO`; sin él no se consulta (503) y el checkout sigue con
// texto libre. La búsqueda sale con el botón, con Enter o tras una pausa larga al
// escribir; el límite de 1 req/s y la caché valen igual para todas.

import { BuscadorOsm, ErrorBusqueda } from "@/lib/direccion-osm";

export const dynamic = "force-dynamic";

// Una instancia por proceso: la cola de 1 req/s y la caché valen para todos.
let buscador: BuscadorOsm | null = null;

function buscadorDelServidor(): BuscadorOsm | null {
  const contacto = process.env["TUKIT_NOMINATIM_CONTACTO"]?.trim();
  if (!contacto) return null;
  buscador ??= new BuscadorOsm({ contacto, fetchFn: fetch });
  return buscador;
}

function error(estado: number, codigo: string, mensaje: string): Response {
  return Response.json({ error: codigo, mensaje }, { status: estado });
}

export async function GET(peticion: Request): Promise<Response> {
  const parametros = new URL(peticion.url).searchParams;
  const consulta = parametros.get("q") ?? "";
  const osm = buscadorDelServidor();
  if (!osm) {
    return error(503, "buscador_no_configurado", "La búsqueda de direcciones no está disponible.");
  }
  try {
    const candidatos = await osm.buscar(consulta);
    return Response.json({ candidatos }, { headers: { "Cache-Control": "private, max-age=300" } });
  } catch (causa) {
    if (causa instanceof ErrorBusqueda) return error(causa.estado, causa.codigo, causa.message);
    console.error("[tukit] búsqueda de dirección", causa);
    return error(502, "buscador_no_disponible", "No pudimos consultar el mapa ahora.");
  }
}
