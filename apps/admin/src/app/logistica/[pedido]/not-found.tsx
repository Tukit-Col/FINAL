// El 404 del detalle: casi siempre es un codigo mal pegado, y la salida util
// es volver al tablero, que busca por el codigo corto.

import Link from "next/link";
import styles from "./Detalle.module.css";

export default function PedidoNoExiste() {
  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/logistica">← Logística</Link>
      </nav>
      <section className={styles.encabezado}>
        <div className={styles.identidad}>
          <h1>Ese pedido no existe.</h1>
          <p>
            Revisa el identificador. Desde el tablero puedes buscar por el código corto de 8
            letras que ve el acudiente.
          </p>
        </div>
      </section>
    </div>
  );
}
