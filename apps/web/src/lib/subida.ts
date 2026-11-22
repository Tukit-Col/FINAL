export const MAX_BYTES_ARCHIVO = 10 * 1024 * 1024;
export const MAX_BYTES_PETICION = 4 * MAX_BYTES_ARCHIVO + 1024 * 1024;

const TIPOS_ADMITIDOS = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);

export function cuerpoDemasiadoGrande(peticion: Request, maximo = MAX_BYTES_PETICION): boolean {
  const declarado = Number(peticion.headers.get("content-length"));
  return Number.isFinite(declarado) && declarado > maximo;
}

export function motivoDeRechazo(archivo: { size: number; type: string }): string | null {
  if (archivo.size > MAX_BYTES_ARCHIVO) {
    return "El archivo pesa más de 10 MB. Prueba con una foto más liviana o con el PDF del colegio.";
  }
  if (archivo.type && !TIPOS_ADMITIDOS.has(archivo.type)) {
    return "Solo recibimos PDF, JPG, PNG o WEBP.";
  }
  return null;
}
