import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import styles from "./ui.module.css";

export default function EstadoVacio({
  titulo,
  children,
  icono,
}: {
  titulo: string;
  children?: ReactNode;
  icono?: ReactNode;
}) {
  return (
    <div className={styles.vacio} role="status">
      <span className={styles.vacioIcono} aria-hidden="true">
        {icono ?? <Inbox size={20} strokeWidth={2} />}
      </span>
      <div>
        <p className={styles.vacioTitulo}>{titulo}</p>
        {children ? <div className={styles.vacioTexto}>{children}</div> : null}
      </div>
    </div>
  );
}

export { styles as estilosVacio };
