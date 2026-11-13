// Barras horizontales (equivalente ligero de `chart-area` para conteos sin
// serie temporal): el largo compara los valores y el color dice la gravedad.
// Cada fila es un enlace a su vista filtrada. La barra crece una vez (CSS).

import Link from "next/link";
import styles from "./Barras.module.css";

export interface FilaBarra {
  clave: string;
  etiqueta: string;
  valor: number;
  href: string;
  tono?: "normal" | "critico" | "aviso";
}

export default function Barras({ filas, maximo }: { filas: readonly FilaBarra[]; maximo?: number }) {
  const tope = Math.max(maximo ?? 0, ...filas.map((f) => f.valor), 1);
  return (
    <ul className={styles.barras}>
      {filas.map((f, i) => (
        <li key={f.clave}>
          <Link href={f.href} className={styles.fila}>
            <span className={styles.etiqueta}>{f.etiqueta}</span>
            <span className={`${styles.valor} cifra ${f.tono === "critico" && f.valor > 0 ? styles.critico : ""}`}>
              {f.valor}
            </span>
            <span className={styles.pista} aria-hidden="true">
              <span
                className={`${styles.relleno} ${styles[f.tono ?? "normal"]}`}
                style={{ width: `${(f.valor / tope) * 100}%`, animationDelay: `${i * 70}ms` }}
              />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
