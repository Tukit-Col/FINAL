// §11 — el 429 del limite de tasa del gateway (ADR 0047).
//
// El gateway responde `{error: "demasiadas_peticiones", mensaje,
// reintentar_en_segundos}` con `Retry-After`. Lo normal es mostrar su
// `mensaje`, que ya trae la espera; estas funciones cubren lo demas: un 429 sin
// cuerpo (un proxy de por medio) o un cuerpo sin los segundos. Son puras y no
// importan nada, para que el navegador y el servidor usen las mismas.

// La fecha de `Retry-After` en el formato que la RFC 9110 manda generar
// (IMF-fixdate). `Date.parse` sola acepta casi cualquier cosa, hasta "-5".
const FECHA_HTTP = /^[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT$/;

/** Los segundos de `Retry-After`, en segundos o como fecha HTTP; `null` si no se entiende. */
export function segundosDeEspera(retryAfter: string | null, ahora: number = Date.now()): number | null {
  const valor = retryAfter?.trim();
  if (!valor) return null;
  if (/^\d+$/.test(valor)) return Math.max(1, Number(valor));
  if (!FECHA_HTTP.test(valor)) return null;
  const fecha = Date.parse(valor);
  if (Number.isNaN(fecha)) return null;
  return Math.max(1, Math.ceil((fecha - ahora) / 1000));
}

/** La espera de un 429: la del cuerpo si la trae, si no la de `Retry-After`. */
export function esperaDe429(cuerpo: Record<string, unknown>, retryAfter: string | null): number | null {
  const delCuerpo = cuerpo["reintentar_en_segundos"];
  if (typeof delCuerpo === "number" && Number.isFinite(delCuerpo) && delCuerpo > 0) {
    return Math.ceil(delCuerpo);
  }
  return segundosDeEspera(retryAfter);
}

/** El mismo texto que arma el gateway, para cuando el 429 llega sin el suyo. */
export function mensajeDeEspera(segundos: number | null): string {
  const base = "Hiciste demasiadas peticiones en poco tiempo.";
  if (segundos === null) return `${base} Espera un momento y vuelve a intentarlo.`;
  let espera: string;
  if (segundos < 60) {
    espera = segundos === 1 ? "1 segundo" : `${segundos} segundos`;
  } else {
    const minutos = Math.ceil(segundos / 60);
    espera = minutos === 1 ? "1 minuto" : `${minutos} minutos`;
  }
  return `${base} Vuelve a intentarlo en ${espera}.`;
}

/**
 * El cuerpo de un error con lo que le falte si es un 429: `error`, el `mensaje`
 * con la espera y `reintentar_en_segundos`. Con otro estado lo devuelve igual.
 * Lo usan el cliente del servidor y los ayudantes del navegador, para que todas
 * las pantallas digan lo mismo.
 */
export function conEspera<T extends Record<string, unknown>>(
  estado: number,
  cuerpo: T,
  retryAfter: string | null,
): T {
  if (estado !== 429) return cuerpo;
  const segundos = esperaDe429(cuerpo, retryAfter);
  return {
    ...cuerpo,
    error: typeof cuerpo["error"] === "string" ? cuerpo["error"] : "demasiadas_peticiones",
    mensaje: typeof cuerpo["mensaje"] === "string" ? cuerpo["mensaje"] : mensajeDeEspera(segundos),
    ...(segundos === null ? {} : { reintentar_en_segundos: segundos }),
  };
}
