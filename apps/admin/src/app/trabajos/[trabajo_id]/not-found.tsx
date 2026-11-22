import Link from "next/link";
import styles from "./Detalle.module.css";

export default function TrabajoNoExiste() {
  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/cola">← Cola de revisión</Link>
      </nav>
      <section className={styles.encabezado}>
        <div className={styles.identidad}>
          <h1>Ese trabajo no existe.</h1>
          <p>
            Puede que el identificador esté incompleto, o que el trabajo se haya creado en otro
            entorno: cada backend tiene su propia base, así que un id de otro despliegue no
            aparece aquí.
          </p>
        </div>
      </section>
    </div>
  );
}
