// Un pedido que no existe o que no es del acudiente: el mismo aviso para los
// dos, para no confirmar que un id ajeno existe.

import Link from "next/link";
import styles from "./PaginaPedido.module.css";

export default function PedidoNoEncontrado() {
  return (
    <div className={styles.pagina}>
      <div className={styles.contenedor}>
        <section className={styles.tarjeta}>
          <h1 className={styles.titulo}>No encontramos ese pedido</h1>
          <p className={styles.resumen}>
            Puede que el enlace esté incompleto o que el pedido sea de otra cuenta.
          </p>
          <Link href="/dashboard#pedidos" className={styles.boton}>
            Ver mis pedidos
          </Link>
        </section>
      </div>
    </div>
  );
}
