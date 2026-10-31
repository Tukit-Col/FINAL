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
    // El 429 del limite de tasa sale con su `Retry-After`, tal como lo dio el
    // gateway (ADR 0047): el navegador no tiene que adivinar cuanto esperar.
    const espera = causa.detalle["reintentar_en_segundos"];
    const cabeceras: Record<string, string> =
      causa.estado === 429 && typeof espera === "number" ? { "Retry-After": String(espera) } : {};
    return Response.json({ error, mensaje, ...resto }, { status: causa.estado, headers: cabeceras });
  }

  console.error("[tukit] fallo no controlado", causa);
  return Response.json(
    { error: "error_interno", mensaje: "Algo se rompió de nuestro lado. Intenta de nuevo." },
    { status: 500 },
  );
}
