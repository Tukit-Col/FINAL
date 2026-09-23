import { FlaskConical, PlugZap } from "lucide-react";
import styles from "./CintaOrigen.module.css";

interface Props {
  nombre: "api" | "simulado";
  detalle: string;
}

/**
 * Dice de donde salen los datos de la pantalla.
 *
 * No es una ayuda de depuracion: mientras el backend se construye en paralelo,
 * la pregunta "esto que veo es de verdad?" se hace varias veces al dia, y una
 * pantalla que se ve completa con datos simulados y no lo dice es una forma
 * barata de creer que algo esta listo cuando no lo esta.
 */
export default function CintaOrigen({ nombre, detalle }: Props) {
  if (nombre === "api") {
    return (
      <div className={`${styles.cinta} ${styles.api}`}>
        <PlugZap size={15} aria-hidden="true" strokeWidth={2.4} />
        Conectado al backend en <code>{detalle}</code> · sesión vía gateway → identidad
      </div>
    );
  }

  return (
    <div className={`${styles.cinta} ${styles.simulado}`}>
      <FlaskConical size={15} aria-hidden="true" strokeWidth={2.4} />
      Datos simulados: catálogo, listas y usuarios de prueba del repositorio, sin backend.
      <span className={styles.pista}>
        Sesión de demostración: cualquier clave entra · cambia con <code>TUKIT_ORIGEN_DATOS=api</code>
      </span>
    </div>
  );
}
