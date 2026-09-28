import Link from "next/link";
import { Users, Package, PlusCircle } from "lucide-react";
import styles from "./Sidebar.module.css";

// Navegacion honesta de la cuenta. El nombre de la cuenta sale de la sesion
// real (la pagina lo resuelve a nombre o correo y lo pasa como prop); el nav
// sigue apuntando solo a destinos reales: las dos secciones de esta misma
// pagina (ancla interna) y el flujo real de armado (/empezar). Nada de /perfil,
// /logout u otras rutas que el backend aun no sirve.
const navItems = [
  { id: "hijos", label: "Perfiles de hijos", href: "#hijos", icon: Users },
  { id: "pedidos", label: "Mis pedidos", href: "#pedidos", icon: Package },
];

export default function Sidebar({ nombreCuenta }: { nombreCuenta: string }) {
  return (
    <aside className={styles.sidebar}>
      {/* Cuenta */}
      <div className={styles.sidebar__account}>
        <div className={styles["sidebar__account-label"]}>Mi cuenta</div>
        <div className={styles["sidebar__account-name"]}>{nombreCuenta}</div>
      </div>

      <nav className={styles.sidebar__nav}>
        {navItems.map(({ id, label, href, icon: Icon }) => (
          <a key={id} href={href} className={styles.sidebar__item}>
            <span className={styles.sidebar__icon}>
              <Icon size={17} strokeWidth={2} aria-hidden="true" />
            </span>
            {label}
          </a>
        ))}

        <div className={styles.sidebar__separator} />

        {/* Unico enlace a ruta real: el flujo de armado de kit. */}
        <Link href="/empezar" className={styles["sidebar__cta"]}>
          <span className={styles.sidebar__icon}>
            <PlusCircle size={17} strokeWidth={2} aria-hidden="true" />
          </span>
          Nuevo pedido
        </Link>
      </nav>
    </aside>
  );
}
