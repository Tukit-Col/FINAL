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

  console.error("[tukit-admin] fallo no controlado", causa);
  return Response.json(
    { error: "error_interno", mensaje: "Algo se rompio de nuestro lado. Intenta de nuevo." },
    { status: 500 },
  );
}

export const SIN_CONTENIDO = () => new Response(null, { status: 204 });

export async function cuerpoJson<T>(peticion: Request): Promise<T | null> {
  const texto = await peticion.text();
  if (!texto.trim()) return null;
  return JSON.parse(texto) as T;
}
