// La cookie de sesion la comparte todo Tukit: la pone la app web al entrar
// (`POST /api/sesion`), viaja al saltar a este back-office (:3001) por ser del
// mismo sitio, y aqui solo la leemos para cerrarla. El nombre tiene que ser
// identico al de la web (`apps/web/src/lib/sesion.ts`), o el DELETE de este
// lado no encontraria la cookie que puso el otro.
import "server-only";
import { cookies } from "next/headers";

export const COOKIE_SESION = "tukit_sesion";

/** El token crudo de la cookie de sesión, o `undefined` si no hay. Los Server
 *  Components lo reenvían como Bearer cuando el backend exige un permiso del
 *  admin (p. ej. `usuario:leer:nombre` para ver el nombre de un acudiente). No
 *  se valida aquí: el gateway lo hace al recibirlo. */
export async function tokenDeSesion(): Promise<string | undefined> {
  return (await cookies()).get(COOKIE_SESION)?.value;
}
