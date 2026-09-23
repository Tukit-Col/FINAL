// La cookie de sesion la comparte todo Tukit: la pone la app web al entrar
// (`POST /api/sesion`), viaja al saltar a este back-office (:3001) por ser del
// mismo sitio, y aqui solo la leemos para cerrarla. El nombre tiene que ser
// identico al de la web (`apps/web/src/lib/sesion.ts`), o el DELETE de este
// lado no encontraria la cookie que puso el otro.
export const COOKIE_SESION = "tukit_sesion";
