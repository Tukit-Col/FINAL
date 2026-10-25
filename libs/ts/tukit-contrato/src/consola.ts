// §7 — la consola interna exige la sesion del equipo (contrato 1.12).
//
// El gateway rechaza toda ruta `/v1/admin/*` sin un Bearer de admin u operador.
// La consola (apps/admin) tiene el token en la cookie `tukit_sesion`, y en vez
// de pasarlo a mano en cada metodo del cliente, el origen de datos lo pega a
// toda llamada de consola. Es puro y no importa nada, para poder probarlo sin
// Next.

const PREFIJO_CONSOLA = "/v1/admin";

// Las escrituras de consola que nacieron fuera de `/v1/admin` (editar, retirar
// y reclasificar un producto; editar un colegio). El gateway las cierra por
// metodo; aqui basta la ruta: la lectura de esas mismas rutas es publica y un
// Bearer de mas no la cambia.
const CONSOLA_FUERA_DE_ADMIN = [
  /^\/v1\/catalogo\/productos\/[^/]+(\/reclasificar)?$/,
  /^\/v1\/colegios\/[^/]+$/,
];

/** `true` si la ruta (con o sin query) es de la consola interna. */
export function esRutaDeConsola(ruta: string): boolean {
  const camino = ruta.split("?", 1)[0] ?? "";
  if (CONSOLA_FUERA_DE_ADMIN.some((patron) => patron.test(camino))) return true;
  return camino === PREFIJO_CONSOLA || camino.startsWith(`${PREFIJO_CONSOLA}/`);
}

/** El `Authorization` que lleva una llamada de consola, o nada si la ruta no es
 *  de consola o no hay token. Solo la consola: el resto de rutas sigue igual,
 *  para no cambiar lo que la web manda en nombre del acudiente. */
export function autorizacionDeConsola(ruta: string, token: string | undefined): Record<string, string> {
  if (!token || !esRutaDeConsola(ruta)) return {};
  return { Authorization: `Bearer ${token}` };
}
