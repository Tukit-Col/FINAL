import Link from "next/link";
import styles from "./Cliente.module.css";

export default function ClienteNoExiste() {
  return (
    <div className={styles.pagina}>
      <nav className={styles.migas} aria-label="Ruta">
        <Link href="/clientes">Clientes</Link>
      </nav>
      <section className={styles.bloque}>
        <h1>Ese cliente no existe.</h1>
        <p className={styles.tenue}>
          Revisa el enlace o búscalo por correo en el <Link href="/clientes">padrón de clientes</Link>.
        </p>
      </section>
    </div>
  );
}
