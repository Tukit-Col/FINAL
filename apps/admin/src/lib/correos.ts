import type { EstadoCorreo, FiltrosCorreos } from "@tukit/contrato";

type Parametros = Record<string, string | string[] | undefined>;

export const ESTADOS_CORREO: readonly EstadoCorreo[] = ["enviada", "fallida", "omitida"];

export const ETIQUETA_ESTADO_CORREO: Record<EstadoCorreo, string> = {
  enviada: "Enviada",
  fallida: "Fallida",
  omitida: "Omitida",
};

const primero = (valor: string | string[] | undefined): string =>
  (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";

export function leerFiltrosCorreos(p: Parametros): FiltrosCorreos {
  const estado = primero(p.estado);
  const filtros: FiltrosCorreos = {};
  if ((ESTADOS_CORREO as readonly string[]).includes(estado)) filtros.estado = estado as EstadoCorreo;
  for (const clave of ["plantilla", "pedido", "caso"] as const) {
    const valor = primero(p[clave]);
    if (valor) filtros[clave] = valor;
  }
  return filtros;
}

export function hrefCorreos(
  filtros: FiltrosCorreos,
  cambios: Partial<Record<keyof FiltrosCorreos, string | undefined>> = {},
): string {
  const combinados: Record<string, string | number | undefined> = { ...filtros, ...cambios };
  const qs = new URLSearchParams();
  for (const [clave, valor] of Object.entries(combinados)) {
    if (valor) qs.set(clave, String(valor));
  }
  return qs.size ? `/correos?${qs}` : "/correos";
}

export function hayFiltrosCorreos(filtros: FiltrosCorreos): boolean {
  return Object.values(filtros).some((v) => v !== undefined && v !== "");
}

export function explicarDetalle(detalle: string | null): string {
  if (!detalle) return "Sin detalle";
  if (detalle === "smtp") return "Entregado al servidor de correo";
  if (detalle === "consola") return "Modo consola: no salió de este equipo";
  if (detalle === "destino_no_enviable") return "Dirección de prueba o inexistente: no se intentó";
  if (detalle === "sin_correo") return "El usuario no tiene correo";
  if (detalle.startsWith("smtp_error")) return `El servidor de correo falló (${detalle.split(": ")[1] ?? "error"})`;
  if (detalle.startsWith("error")) return `Error al armar o enviar (${detalle.split(": ")[1] ?? "error"})`;
  return detalle;
}
