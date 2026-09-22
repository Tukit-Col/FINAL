import { ErrorTukit } from "@tukit/contrato";

/**
 * Traduce un fallo a la forma de error del §11.
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

  console.error("[tukit] fallo no controlado", causa);
  return Response.json(
    { error: "error_interno", mensaje: "Algo se rompio de nuestro lado. Intenta de nuevo." },
    { status: 500 },
  );
}
