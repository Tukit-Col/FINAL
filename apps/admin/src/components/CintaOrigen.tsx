import styles from "./CintaOrigen.module.css";

interface Props {
  nombre: "api" | "simulado";
  detalle: string;
}

/**
 * Dice de donde salen los datos de la pantalla.
 *
 * En la consola de admin importa todavia mas que en la app del acudiente:
 * aqui se aprueban trabajos, y aprobar contra el almacen simulado creyendo
 * que es produccion es el error caro de esta pantalla. Por eso el origen
 * simulado muestra tambien la ruta del fichero.
 */
export default function CintaOrigen({ nombre, detalle }: Props) {
  if (nombre === "api") {
    return (
      <div className={`${styles.cinta} ${styles.api}`}>
        <span className={styles.punto} aria-hidden="true" />
        Conectado al backend en <code>{detalle}</code>
      </div>
    );
  }

  return (
    <div className={`${styles.cinta} ${styles.simulado}`}>
      <span className={styles.punto} aria-hidden="true" />
      Datos simulados: lo que apruebes aquí no sale de este equipo.
      <code>{detalle}</code>
      <span className={styles.pista}>
        Cambia con <code>TUKIT_ORIGEN_DATOS=api</code>
      </span>
    </div>
  );
}
