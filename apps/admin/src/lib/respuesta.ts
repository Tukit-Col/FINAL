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
    // El 429 del limite de tasa sale con su `Retry-After`, tal como lo dio el
    // gateway (ADR 0047): el navegador no tiene que adivinar cuanto esperar.
    const espera = causa.detalle["reintentar_en_segundos"];
    const cabeceras: Record<string, string> =
      causa.estado === 429 && typeof espera === "number" ? { "Retry-After": String(espera) } : {};
    return Response.json({ error, mensaje, ...resto }, { status: causa.estado, headers: cabeceras });
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
