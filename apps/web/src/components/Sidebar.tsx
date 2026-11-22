import Link from "next/link";
import { PlusCircle, ShieldCheck } from "lucide-react";
import NavSecciones from "./NavSecciones";
import SalirBoton from "./SalirBoton";
import styles from "./Sidebar.module.css";

export default function Sidebar({ nombreCuenta }: { nombreCuenta: string }) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebar__account}>
        <div className={styles["sidebar__account-label"]}>Mi cuenta</div>
        <div className={styles["sidebar__account-name"]}>{nombreCuenta}</div>
      </div>

      <nav className={styles.sidebar__nav}>
        <NavSecciones />

        <Link href="/privacidad" className={styles.sidebar__item}>
          <span className={styles.sidebar__icon}>
            <ShieldCheck size={17} strokeWidth={2} aria-hidden="true" />
          </span>
          Privacidad y mis datos
        </Link>

        <div className={styles.sidebar__separator} />

        <Link href="/empezar" className={styles["sidebar__cta"]}>
          <span className={styles.sidebar__icon}>
            <PlusCircle size={17} strokeWidth={2} aria-hidden="true" />
          </span>
          Nuevo pedido
        </Link>

        <div className={styles.sidebar__salir}>
          <SalirBoton />
        </div>
      </nav>
    </aside>
  );
}
