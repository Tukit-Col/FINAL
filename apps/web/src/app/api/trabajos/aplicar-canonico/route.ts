// `POST /api/trabajos/aplicar-canonico` — la ruta rapida del acudiente.
//
// Un (colegio, grado) ya publicado tiene 3 kits validados: en vez de subir un
// PDF y entrar a la cola, el acudiente aplica su nivel + personaje y se le arma
// el pedido al vuelo. Misma costura de siempre: el navegador no toca el backend,
// el origen se resuelve aqui, en el servidor.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { AplicarCanonico } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";

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

  try {
    const aplicado = await origenDeDatos().aplicarCanonico(cuerpo);
    return Response.json(aplicado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
