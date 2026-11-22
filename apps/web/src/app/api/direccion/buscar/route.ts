import { BuscadorOsm, ErrorBusqueda } from "@/lib/direccion-osm";

export const dynamic = "force-dynamic";

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
