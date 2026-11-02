// Los datos del responsable que el equipo debe completar antes de publicar.
//
// Ninguno se inventa: cada valor entre corchetes es un pendiente del equipo y la
// pantalla lo marca para que no pase por dato real. `VERSION_TEXTOS_LEGALES`
// es la misma que Identidad guarda al registrar la aceptación del titular
// (`_VERSION_TERMINOS_TITULAR`): si el texto cambia, sube en los dos lados.

export const VERSION_TEXTOS_LEGALES = "2026-11";
export const FECHA_VIGENCIA = "1 de noviembre de 2026";

export const RESPONSABLE = {
  nombre: "Tukit",
  razonSocial: "[Razón social]",
  nit: "[NIT]",
  domicilio: "[Dirección y ciudad]",
  correo: "[correo de contacto]",
  telefono: "[teléfono de contacto]",
} as const;

/** Un valor es un pendiente si todavía está entre corchetes. */
export function esPendiente(valor: string): boolean {
  return /^\[.*\]$/.test(valor.trim());
}
