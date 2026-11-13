// Barras horizontales (equivalente ligero de `chart-area` para conteos sin
// serie temporal): el largo compara los valores y el color dice la gravedad.
// Cada fila es un enlace a su vista filtrada. La barra crece una vez (CSS).
// `fina` baja el peso visual cuando todas valen casi lo mismo (no es ranking);
// `nota` es una marca corta junto a la etiqueta (p. ej. "acudiente esperando").

import Link from "next/link";
import type { ReactNode } from "react";
import { proporcion } from "@/lib/graficos";
import styles from "./Barras.module.css";

export interface FilaBarra {
  clave: string;
  etiqueta: string;
  valor: number;
  href: string;
  tono?: "normal" | "critico" | "aviso" | "suave";
  /** Texto del valor si no es solo la cifra ("3 listas"). */
  valorTexto?: string;
  nota?: ReactNode;
}

export default function Barras({
  filas,
  maximo,
  fina = false,
}: {
  filas: readonly FilaBarra[];
  maximo?: number;
  fina?: boolean;
}) {
  const tope = Math.max(maximo ?? 0, ...filas.map((f) => f.valor), 1);
  return (
    <ul className={`${styles.barras} ${fina ? styles.fina : ""}`}>
      {filas.map((f, i) => (
        <li key={f.clave}>
          <Link href={f.href} className={styles.fila}>
            <span className={styles.etiqueta}>
              <span className={styles.texto} title={f.etiqueta}>
                {f.etiqueta}
              </span>
              {f.nota ? <span className={styles.nota}>{f.nota}</span> : null}
            </span>
            <span className={`${styles.valor} cifra ${f.tono === "critico" && f.valor > 0 ? styles.critico : ""}`}>
              {f.valorTexto ?? f.valor}
            </span>
            <span className={styles.pista} aria-hidden="true">
              <span
                className={`${styles.relleno} ${styles[f.tono ?? "normal"]}`}
                style={{ width: `${proporcion(f.valor, tope, 0)}%`, animationDelay: `${i * 70}ms` }}
              />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
