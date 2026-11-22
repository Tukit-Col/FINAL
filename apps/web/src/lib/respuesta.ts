import { ErrorTukit } from "@tukit/contrato";

export function respuestaDeError(causa: unknown): Response {
  if (causa instanceof ErrorTukit) {
    const { error, mensaje, ...resto } = {
      error: causa.codigo,
      mensaje: causa.message,
      ...causa.detalle,
    };
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
