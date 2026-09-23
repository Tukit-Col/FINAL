// El 404 del §11 con cara de consola: un identificador mal pegado es el error
// mas comun de llegar aqui, y la salida util es volver a la cola.

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
            entorno: con el origen simulado los trabajos viven en un fichero temporal del
            equipo y se pierden al limpiarlo.
          </p>
        </div>
      </section>
    </div>
  );
}
