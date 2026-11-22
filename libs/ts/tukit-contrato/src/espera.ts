// El 429 del límite de tasa del gateway.
//
// Decisiones:
// - El gateway responde `{error: "demasiadas_peticiones", mensaje, reintentar_en_segundos}` con
//   `Retry-After`. Lo normal es mostrar su `mensaje`; estas funciones cubren un 429 sin cuerpo (un proxy
//   de por medio) o sin los segundos.
// - Son puras y no importan nada, para que el navegador y el servidor usen las mismas.
// - La fecha de `Retry-After` se acepta solo en el formato IMF-fixdate de la RFC 9110: `Date.parse`
//   acepta casi cualquier cosa, hasta "-5".

const FECHA_HTTP = /^[A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT$/;

export function segundosDeEspera(retryAfter: string | null, ahora: number = Date.now()): number | null {
  const valor = retryAfter?.trim();
  if (!valor) return null;
  if (/^\d+$/.test(valor)) return Math.max(1, Number(valor));
  if (!FECHA_HTTP.test(valor)) return null;
  const fecha = Date.parse(valor);
  if (Number.isNaN(fecha)) return null;
  return Math.max(1, Math.ceil((fecha - ahora) / 1000));
}

export function esperaDe429(cuerpo: Record<string, unknown>, retryAfter: string | null): number | null {
  const delCuerpo = cuerpo["reintentar_en_segundos"];
  if (typeof delCuerpo === "number" && Number.isFinite(delCuerpo) && delCuerpo > 0) {
    return Math.ceil(delCuerpo);
  }
  return segundosDeEspera(retryAfter);
}

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
