import Link from "next/link";
import styles from "./Cabecera.module.css";

const ENLACES = [
  { href: "/", texto: "Inicio" },
  { href: "/catalogo", texto: "Catalogo" },
  { href: "/dashboard", texto: "Mi cuenta" },
];

export default function Cabecera() {
  return (
    <header className={styles.cabecera}>
      <div className={styles.interior}>
        <Link href="/" className={styles.logo}>
          <span className={styles.marca} aria-hidden="true">
            <svg viewBox="0 0 18 18" fill="none">
              <path d="M9 1L16.5 5.25V12.75L9 17L1.5 12.75V5.25L9 1Z" fill="white" fillOpacity="0.9" />
              <path d="M9 5L13 7.5V12L9 14L5 12V7.5L9 5Z" fill="white" />
            </svg>
          </span>
          <span className={styles.nombre}>Tukit</span>
        </Link>

        <nav className={styles.nav} aria-label="Principal">
          {ENLACES.map((enlace) => (
            <Link key={enlace.href} href={enlace.href} className={styles.enlace}>
              {enlace.texto}
            </Link>
          ))}
        </nav>

        <Link href="/empezar" className={styles.accion}>
          Armar mi kit
        </Link>
      </div>
    </header>
  );
}
