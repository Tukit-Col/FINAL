export const VERSION_TEXTOS_LEGALES = "2026-11";
export const FECHA_VIGENCIA = "1 de noviembre de 2026";

export const RESPONSABLE = {
  nombre: "Tukit",
  naturaleza:
    "un proyecto de trabajo de grado de Ingeniería de Sistemas de la Pontificia Universidad Javeriana, que aún no está constituido como empresa",
  domicilio: "Bogotá, Colombia",
  correo: "tukit.ayuda@gmail.com",
} as const;

export function esPendiente(valor: string): boolean {
  return /^\[.*\]$/.test(valor.trim());
}
