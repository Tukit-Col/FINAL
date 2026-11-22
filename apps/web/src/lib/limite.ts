// El 429 del límite de tasa del gateway, visto desde la web.
//
// Decisiones:
// - Un 429 dice "espera", nunca "no tienes sesión" ni "no tienes datos": las lecturas que fallan
//   cerrado (`sesionActual`, `matriculasDeLaSesion`) lo dejan pasar para mostrar el aviso con la
//   espera en vez de mandar a `/ingresar`.
// - Son funciones puras sin imports; reconocen el 429 por su forma (`estado`, `mensaje`, `detalle`).

type ConEstado = Error & { estado: number; detalle?: Record<string, unknown> };

export type AvisoLimite = { mensaje: string; segundos: number | null };

export function esLimiteDeTasa(causa: unknown): causa is ConEstado {
  return causa instanceof Error && (causa as Partial<ConEstado>).estado === 429;
}

export function avisoDeLimite(causa: unknown): AvisoLimite | null {
  if (!esLimiteDeTasa(causa)) return null;
  const segundos = causa.detalle?.["reintentar_en_segundos"];
  return { mensaje: causa.message, segundos: typeof segundos === "number" ? segundos : null };
}

export async function fallaCerradoSalvoLimite<T>(leer: () => Promise<T>, siFalla: T): Promise<T> {
  try {
    return await leer();
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    return siFalla;
  }
}

export function cuentaCreadaSinSesion(causa: unknown): boolean {
  return esLimiteDeTasa(causa) && causa.detalle?.["cuenta_creada"] === true;
}

export function avisoCuentaCreada(causa: Error): string {
  return (
    `${causa.message} Tu cuenta ya quedó creada: cuando pase ese tiempo, presiona ` +
    "«Armar mis kits» otra vez y seguimos con lo que llenaste."
  );
}
