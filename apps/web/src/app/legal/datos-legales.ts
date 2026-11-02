// Los datos del responsable que el equipo debe completar antes de publicar.
//
// Ninguno se inventa: cada valor entre corchetes es un pendiente del equipo y la
// pantalla lo marca para que no pase por dato real. `VERSION_TEXTOS_LEGALES`
// es la misma que Identidad guarda al registrar la aceptación del titular
// (`_VERSION_TERMINOS_TITULAR`): si el texto cambia, sube en los dos lados.

export const VERSION_TEXTOS_LEGALES = "2026-11";
export const FECHA_VIGENCIA = "1 de noviembre de 2026";

// Tukit todavía no está constituido como empresa: no tiene razón social ni NIT,
// y por eso la pantalla no los muestra en vez de dejar un hueco. Tampoco hay
// teléfono de atención; el canal es el correo y los casos de la sección Ayuda.
// Cuando se constituya, se agregan aquí y en las páginas que los citan.
export const RESPONSABLE = {
  nombre: "Tukit",
  naturaleza:
    "un proyecto de trabajo de grado de Ingeniería de Sistemas de la Pontificia Universidad Javeriana, que aún no está constituido como empresa",
  domicilio: "Bogotá, Colombia",
  correo: "tukit.ayuda@gmail.com",
} as const;

/** Un valor es un pendiente si todavía está entre corchetes. */
export function esPendiente(valor: string): boolean {
  return /^\[.*\]$/.test(valor.trim());
}
