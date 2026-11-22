import styles from "../Pago.module.css";
import ProcesandoPrueba from "./ProcesandoPrueba";

export default async function PaginaPagoSimulado({
  searchParams,
}: {
  searchParams: Promise<{ ref?: string | string[]; resultado?: string | string[] }>;
}) {
  const { ref: crudo, resultado: crudoResultado } = await searchParams;
  const ref = Array.isArray(crudo) ? crudo[0] : crudo;
  const resultado = Array.isArray(crudoResultado) ? crudoResultado[0] : crudoResultado;

  if (!ref) {
    return (
      <div className={styles.pagina}>
        <div className={styles.tarjeta}>
          <h1 className={styles.titulo}>No pudimos continuar con el pago</h1>
          <p className={styles.texto}>Vuelve a tu kit e inténtalo de nuevo.</p>
        </div>
      </div>
    );
  }

  const estado = resultado === "rechazado" ? "DECLINED" : "APPROVED";
  const destino = `/pago/resultado?id=${encodeURIComponent(`falsa-${estado}-${ref}`)}`;
  return <ProcesandoPrueba destino={destino} />;
}
