import Link from "next/link";
import styles from "./CabeceraAdmin.module.css";

/** Barra fija de la consola. Un solo enlace: desde cualquier trabajo se vuelve a la cola. */
export default function CabeceraAdmin() {
  return (
    <header className={styles.cabecera}>
      <Link href="/" className={styles.logo}>
        <span className={styles.marca} aria-hidden="true">
          <svg viewBox="0 0 18 18" fill="none">
            <path d="M9 1L16.5 5.25V12.75L9 17L1.5 12.75V5.25L9 1Z" fill="white" fillOpacity="0.9" />
            <path d="M9 5L13 7.5V12L9 14L5 12V7.5L9 5Z" fill="white" />
          </svg>
        </span>
        <span className={styles.nombre}>Tukit</span>
        <span className={styles.consola}>Consola de revisión</span>
      </Link>
      <span className={styles.requisitos}>AD-02 · AD-03 · AD-04 · AD-05 · AD-06 · AD-07</span>
    </header>
  );
}
