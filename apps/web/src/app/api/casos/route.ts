// `GET|POST /api/casos` — los casos (PQRS) del acudiente.
//
// El dueño de un caso es la SESIÓN, no un correo escrito en un formulario: antes
// se aceptaba el correo de cualquiera y el caso quedaba a nombre de otra
// familia. Ahora ambas rutas exigen sesión y el backend (Operación) valida el
// token; un caso ajeno responde 403.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { SolicitudMiCaso } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";

const SIN_SESION = new ErrorTukit(401, "sin_sesion", "Inicia sesión para ver y abrir tus casos.");

export async function GET(): Promise<Response> {
  const token = await tokenDeSesion();
  if (!token) return respuestaDeError(SIN_SESION);
  try {
    return Response.json({ casos: await origenDeDatos().misCasos(token) });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}

export async function POST(peticion: Request): Promise<Response> {
  const token = await tokenDeSesion();
  if (!token) return respuestaDeError(SIN_SESION);

  let cuerpo: Partial<SolicitudMiCaso>;
  try {
    cuerpo = (await peticion.json()) as Partial<SolicitudMiCaso>;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer tu solicitud."),
    );
  }
  // Solo viajan los campos del caso: si el navegador manda un contacto u otro
  // dueño, se ignora.
  const solicitud: SolicitudMiCaso = {
    categoria: cuerpo.categoria as SolicitudMiCaso["categoria"],
    asunto: String(cuerpo.asunto ?? ""),
    descripcion: String(cuerpo.descripcion ?? ""),
    trabajo_id: cuerpo.trabajo_id || null,
    pedido_id: cuerpo.pedido_id || null,
  };
  try {
    const creado = await origenDeDatos().abrirMiCaso(token, solicitud);
    return Response.json(creado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
