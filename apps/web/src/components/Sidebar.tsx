import Link from "next/link";
import { PlusCircle } from "lucide-react";
import NavSecciones from "./NavSecciones";
import SalirBoton from "./SalirBoton";
import styles from "./Sidebar.module.css";

// Navegacion honesta de la cuenta. El nombre de la cuenta sale de la sesion
// real (la pagina lo resuelve a nombre o correo y lo pasa como prop); el nav
// sigue apuntando solo a destinos reales: las secciones de esta misma pagina
// (con desplazamiento suave, en `NavSecciones`) y el flujo real de armado
// (/empezar). Nada de /perfil u otras rutas que el backend aun no sirve; cerrar
// sesion es el mismo `SalirBoton` de la cabecera (DELETE /api/sesion).
export default function Sidebar({ nombreCuenta }: { nombreCuenta: string }) {
  return (
    <aside className={styles.sidebar}>
      {/* Cuenta */}
      <div className={styles.sidebar__account}>
        <div className={styles["sidebar__account-label"]}>Mi cuenta</div>
        <div className={styles["sidebar__account-name"]}>{nombreCuenta}</div>
      </div>

      <nav className={styles.sidebar__nav}>
        <NavSecciones />

        <div className={styles.sidebar__separator} />

        {/* Unico enlace a ruta real: el flujo de armado de kit. */}
        <Link href="/empezar" className={styles["sidebar__cta"]}>
          <span className={styles.sidebar__icon}>
            <PlusCircle size={17} strokeWidth={2} aria-hidden="true" />
          </span>
          Nuevo pedido
        </Link>

        {/* En el celular la cabecera esconde "Cerrar sesión" por espacio: aquí,
            en la cuenta, es donde se cierra. En escritorio ya está arriba. */}
        <div className={styles.sidebar__salir}>
          <SalirBoton />
        </div>
      </nav>
    </aside>
  );
}
