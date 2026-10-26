// El 429 del limite de tasa del gateway (ADR 0047), visto desde la web.
//
// Un 429 dice "espera", nunca "no tienes sesion" ni "no tienes datos": la
// cookie sigue valiendo y los datos siguen ahi. Las lecturas que fallan
// cerrado (`sesionActual`, `matriculasDeLaSesion`) lo dejan pasar para que la
// pantalla muestre el aviso con la espera, en vez de mandar a `/ingresar` o
// pintar "todavia no has registrado a tus hijos".
//
// Puras y sin importar nada: reconocen el 429 por su forma (`estado`, el
// `mensaje` que ya trae la espera, `detalle`), que es la misma de `ErrorTukit`
// en el servidor y de `FalloApi` en el navegador.

type ConEstado = Error & { estado: number; detalle?: Record<string, unknown> };

export type AvisoLimite = { mensaje: string; segundos: number | null };

export function esLimiteDeTasa(causa: unknown): causa is ConEstado {
  return causa instanceof Error && (causa as Partial<ConEstado>).estado === 429;
}

/** El mensaje y la espera de un 429, o `null` si la causa es otra. */
export function avisoDeLimite(causa: unknown): AvisoLimite | null {
  if (!esLimiteDeTasa(causa)) return null;
  const segundos = causa.detalle?.["reintentar_en_segundos"];
  return { mensaje: causa.message, segundos: typeof segundos === "number" ? segundos : null };
}

/** Lee y, si falla, devuelve `siFalla`; salvo un 429, que se propaga. */
export async function fallaCerradoSalvoLimite<T>(leer: () => Promise<T>, siFalla: T): Promise<T> {
  try {
    return await leer();
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    return siFalla;
  }
}

/**
 * El 429 del login que `/api/registro` hace enseguida del alta: la cuenta SI
 * quedo creada, pero sin sesion, porque entrar comparte el cupo estricto de la
 * IP (H-R-01). La ruta lo marca con `cuenta_creada: true` en el detalle.
 */
export function cuentaCreadaSinSesion(causa: unknown): boolean {
  return esLimiteDeTasa(causa) && causa.detalle?.["cuenta_creada"] === true;
}

/** El mensaje del 429 (con su espera) y que hacer despues, sin perder lo llenado. */
export function avisoCuentaCreada(causa: Error): string {
  return (
    `${causa.message} Tu cuenta ya quedó creada: cuando pase ese tiempo, presiona ` +
    "«Armar mis kits» otra vez y seguimos con lo que llenaste."
  );
}
