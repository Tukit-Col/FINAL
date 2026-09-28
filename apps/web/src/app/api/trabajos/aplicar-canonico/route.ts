// `POST /api/trabajos/aplicar-canonico` — la ruta rapida del acudiente.
//
// Un (colegio, grado) ya publicado tiene 3 kits validados: en vez de subir un
// PDF y entrar a la cola, el acudiente aplica su nivel + personaje y se le arma
// el pedido al vuelo. Misma costura de siempre: el navegador no toca el backend,
// el origen se resuelve aqui, en el servidor.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AplicarCanonico } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { sesionActual } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  let cuerpo: AplicarCanonico;
  try {
    cuerpo = (await peticion.json()) as AplicarCanonico;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del formulario."),
    );
  }

  // La ruta rapida debe tener dueño: el usuario_id lo pone el servidor desde la
  // cookie de sesion, NUNCA el navegador (que podria mentir). Sin sesion, el
  // trabajo queda anonimo igual que hoy (usuario_id undefined -> se omite -> NULL).
  const sesion = await sesionActual();
  const cuerpoConUsuario: AplicarCanonico = { ...cuerpo, usuario_id: sesion?.usuario_id };

  try {
    const aplicado = await origenDeDatos().aplicarCanonico(cuerpoConUsuario);
    return Response.json(aplicado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
