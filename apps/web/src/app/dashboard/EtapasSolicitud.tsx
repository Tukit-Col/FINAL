// La línea de etapas de una solicitud en el panel del acudiente. El dashboard
// solo tiene el `estado` del trabajo (`TrabajoResumen`, sin `etapas[]`), así que
// los pasos se derivan del estado: hasta dónde llegó la solicitud, sin un fetch
// extra por fila. Es el mismo relato que `PantallaEspera` cuenta a pleno, pero
// resumido a una tira horizontal para verlo de un vistazo entre varias
// solicitudes. Server component: sin estado ni motion, solo pinta.
import type { EstadoTrabajo } from "@tukit/contrato";
import styles from "./Dashboard.module.css";

// Los hitos del pipeline en orden, como se los nombra al acudiente. El índice en
// esta lista es "hasta dónde llegó": todo lo anterior queda hecho, el actual en
// curso, lo siguiente pendiente.
const PASOS = ["En cola", "Armando", "Revisión", "Listo"] as const;

// A qué paso llegó cada estado. `fallido` no avanza: se marca aparte como error.
const PASO_ALCANZADO: Record<EstadoTrabajo, number> = {
  encolado: 0,
  procesando: 1,
  espera_revision: 2,
  publicado: 3,
  fallido: 0,
};

export default function EtapasSolicitud({ estado }: { estado: EstadoTrabajo }) {
  const fallido = estado === "fallido";
  const alcanzado = PASO_ALCANZADO[estado];
  const publicado = estado === "publicado";

  return (
    <ol className={styles.etapas} aria-label="Progreso de la solicitud">
      {PASOS.map((paso, i) => {
        // Con el trabajo publicado todos los pasos quedan hechos; si no, el paso
        // alcanzado está "en curso" y los previos "hechos".
        const clase = fallido
          ? styles.etapaPendiente
          : publicado || i < alcanzado
            ? styles.etapaHecha
            : i === alcanzado
              ? styles.etapaEnCurso
              : styles.etapaPendiente;
        return (
          <li key={paso} className={`${styles.etapaChip} ${clase}`}>
            <span className={styles.etapaDot} aria-hidden="true" />
            {paso}
          </li>
        );
      })}
      {fallido && <li className={styles.etapaFallida}>No pudimos terminarlo</li>}
    </ol>
  );
}
