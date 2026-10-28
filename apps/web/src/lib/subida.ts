// Los topes de una subida, antes de leerla. `formData()` carga el cuerpo entero
// en memoria y el backend lo vuelve a leer completo (y cada archivo cuesta una
// llamada a Gemini), asi que un archivo enorme o que no es una lista se corta
// aqui, en la puerta de la web, con el mismo tope que promete la pantalla.

// "PDF, JPG, PNG o WEBP · hasta 10 MB" (`FormularioEmpezar`).
export const MAX_BYTES_ARCHIVO = 10 * 1024 * 1024;
// Un archivo por hijo (`MAX_HIJOS` = 4) mas el resto del formulario.
export const MAX_BYTES_PETICION = 4 * MAX_BYTES_ARCHIVO + 1024 * 1024;

const TIPOS_ADMITIDOS = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);

/** El `Content-Length` declarado supera el tope. Sin cabecera no se adivina. */
export function cuerpoDemasiadoGrande(peticion: Request, maximo = MAX_BYTES_PETICION): boolean {
  const declarado = Number(peticion.headers.get("content-length"));
  return Number.isFinite(declarado) && declarado > maximo;
}

/** El motivo por el que un archivo no se acepta, o `null` si pasa. Un tipo
 *  vacio se deja pasar: algunos navegadores no lo informan y el backend lo
 *  vuelve a mirar al percibirlo. */
export function motivoDeRechazo(archivo: { size: number; type: string }): string | null {
  if (archivo.size > MAX_BYTES_ARCHIVO) {
    return "El archivo pesa más de 10 MB. Prueba con una foto más liviana o con el PDF del colegio.";
  }
  if (archivo.type && !TIPOS_ADMITIDOS.has(archivo.type)) {
    return "Solo recibimos PDF, JPG, PNG o WEBP.";
  }
  return null;
}
