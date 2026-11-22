const PREFIJO_CONSOLA = "/v1/admin";

const CONSOLA_FUERA_DE_ADMIN = [
  /^\/v1\/catalogo\/productos\/[^/]+(\/reclasificar)?$/,
  /^\/v1\/colegios\/[^/]+$/,
];

export function esRutaDeConsola(ruta: string): boolean {
  const camino = ruta.split("?", 1)[0] ?? "";
  if (CONSOLA_FUERA_DE_ADMIN.some((patron) => patron.test(camino))) return true;
  return camino === PREFIJO_CONSOLA || camino.startsWith(`${PREFIJO_CONSOLA}/`);
}

export function autorizacionDeConsola(ruta: string, token: string | undefined): Record<string, string> {
  if (!token || !esRutaDeConsola(ruta)) return {};
  return { Authorization: `Bearer ${token}` };
}
