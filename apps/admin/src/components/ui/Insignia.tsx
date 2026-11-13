// Insignia de estado: texto corto sobre fondo tenue con su borde. No es enlace
// (vive dentro de filas que ya lo son; `Chip` es el filtro clicable). El color
// acompaña al texto, nunca lo reemplaza.

import type { ReactNode } from "react";
import type { TonoEstado } from "@/lib/graficos";
import styles from "./ui.module.css";

const CLASE: Record<TonoEstado, string> = {
  exito: styles.insigniaExito,
  aviso: styles.insigniaAviso,
  peligro: styles.insigniaPeligro,
  info: styles.insigniaInfo,
  neutro: styles.insigniaNeutro,
};

export default function Insignia({ tono, children }: { tono: TonoEstado; children: ReactNode }) {
  return <span className={`${styles.insignia} ${CLASE[tono]}`}>{children}</span>;
}
