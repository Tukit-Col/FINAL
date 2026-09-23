// `GET /api/catalogo/propuestas` — la cola de curaduría proactiva (P4c bis).
//
// Igual que la búsqueda de productos: el navegador no habla con el backend,
// manda el querystring aquí y este handler lo traduce a `colaPropuestas` contra
// el origen del servidor, donde la URL y el token del backend se quedan. Solo
// lectura, pero vive como Route Handler porque la cola se refresca de forma
// interactiva (tras aprobar/rechazar/encolar) sin recargar la página.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

export async function GET(peticion: Request): Promise<Response> {
  const params = new URL(peticion.url).searchParams;
  const concepto = params.get("concepto") ?? undefined;

  try {
    const propuestas = await origenDeDatos().colaPropuestas(concepto);
    return Response.json(propuestas, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
