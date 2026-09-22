import { ErrorTukit } from "@tukit/contrato";

/**
 * Traduce un fallo a la forma de error del §11.
 *
 * Copiado de `apps/web` a proposito y no importado: son dos aplicaciones
 * independientes, y compartir el borde HTTP las obligaria a desplegarse
 * juntas justo donde tienen usuarios distintos.
 *
 * La regla que impone: nunca se devuelve al cliente lo que el cliente acaba de
 * enviar. El manejador de validacion del sistema anterior devolvia la
 * contrasena recibida, y es uno de los defectos ya documentados. Por eso un
 * error que no sea `ErrorTukit` se colapsa a un mensaje generico y el detalle
 * se queda en el log del servidor.
 */
export function respuestaDeError(causa: unknown): Response {
  if (causa instanceof ErrorTukit) {
    const { error, mensaje, ...resto } = {
      error: causa.codigo,
      mensaje: causa.message,
      ...causa.detalle,
    };
    return Response.json({ error, mensaje, ...resto }, { status: causa.estado });
  }

  console.error("[tukit-admin] fallo no controlado", causa);
  return Response.json(
    { error: "error_interno", mensaje: "Algo se rompio de nuestro lado. Intenta de nuevo." },
    { status: 500 },
  );
}

/** Las acciones del §7 no devuelven cuerpo: lo unico que importa es que pasaron. */
export const SIN_CONTENIDO = () => new Response(null, { status: 204 });

/** Lee el JSON de una peticion de escritura, o `null` si no vino ninguno. */
export async function cuerpoJson<T>(peticion: Request): Promise<T | null> {
  const texto = await peticion.text();
  if (!texto.trim()) return null;
  return JSON.parse(texto) as T;
}
