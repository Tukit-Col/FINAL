// Esqueleto de carga para los `loading.tsx` de las rutas: la forma de la
// pantalla (titulo, chips, filas) mientras llegan los datos. aria-busy en el
// contenedor; los bloques son decorativos.

import styles from "./ui.module.css";

export function Bloque({ ancho = "100%", alto = 16 }: { ancho?: string | number; alto?: number }) {
  return <span className={styles.esqueleto} style={{ width: ancho, height: alto }} aria-hidden="true" />;
}

export default function EsqueletoPagina({ filas = 8, chips = 4 }: { filas?: number; chips?: number }) {
  return (
    <div className={styles.esqueletoPagina} aria-busy="true" aria-live="polite">
      <span className={styles.soloLector}>
        Cargando…
      </span>
      <Bloque ancho={180} alto={28} />
      <div className={styles.chips}>
        {Array.from({ length: chips }, (_, i) => (
          <Bloque key={i} ancho={110} alto={44} />
        ))}
      </div>
      <div className={styles.esqueletoFilas}>
        {Array.from({ length: filas }, (_, i) => (
          <Bloque key={i} alto={20} />
        ))}
      </div>
    </div>
  );
}
