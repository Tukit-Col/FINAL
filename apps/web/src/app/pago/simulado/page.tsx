import Link from "next/link";
import styles from "../Pago.module.css";

// Pasarela de mentira para WOMPI_MODO=falso: el backend manda aqui en vez de
// a Wompi, y los dos botones vuelven a la pagina de resultado con un id falso.
export default async function PaginaPagoSimulado({
  searchParams,
}: {
  searchParams: Promise<{ ref?: string | string[] }>;
}) {
  const { ref: crudo } = await searchParams;
  const ref = Array.isArray(crudo) ? crudo[0] : crudo;
  const destino = (estado: "APPROVED" | "DECLINED") =>
    `/pago/resultado?id=${encodeURIComponent(`falsa-${estado}-${ref}`)}`;

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta}>
        <h1 className={styles.titulo}>Pasarela simulada (modo de pruebas sin Wompi)</h1>
        {ref ? (
          <div className={styles.acciones}>
            <Link href={destino("APPROVED")} className={styles.pagar}>
              Aprobar pago
            </Link>
            <Link href={destino("DECLINED")} className={`${styles.pagar} ${styles.secundario}`}>
              Rechazar pago
            </Link>
          </div>
        ) : (
          <p className={styles.texto}>Falta la referencia del pago.</p>
        )}
      </div>
    </div>
  );
}
