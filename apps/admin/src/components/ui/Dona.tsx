// Dona SVG ligera (port de `chart-donut` de sf-design-stack, sin GSAP ni
// runtime): el anillo se dibuja una vez con una animacion CSS de
// stroke-dashoffset, de 12 en punto en sentido horario. La leyenda es la
// fuente accesible: cada fila es un enlace con su cifra y su porcentaje; el
// SVG va aria-hidden. Con prefers-reduced-motion el anillo aparece completo.

import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./Dona.module.css";

export interface SegmentoDona {
  clave: string;
  etiqueta: string;
  valor: number;
  href: string;
  /** Color CSS (var(--token) o hex). */
  color: string;
}

const R = 44;
const C = 2 * Math.PI * R;

export default function Dona({
  segmentos,
  centro,
  pie,
  compacta = false,
}: {
  segmentos: readonly SegmentoDona[];
  /** Texto bajo la cifra central. */
  centro: string;
  pie?: ReactNode;
  /** Anillo chico (resumen dentro de una tarjeta, no el grafico principal). */
  compacta?: boolean;
}) {
  const total = segmentos.reduce((t, s) => t + Math.max(0, s.valor), 0);
  const visibles = segmentos.filter((s) => s.valor > 0);
  const arcos = visibles.map((s, i) => ({
    ...s,
    i,
    largo: (s.valor / total) * C,
    inicio: visibles.slice(0, i).reduce((t, o) => t + (o.valor / total) * C, 0),
  }));

  return (
    <div className={`${styles.dona} ${compacta ? styles.compacta : ""}`}>
      <div className={styles.anillo}>
        <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
          <circle cx="60" cy="60" r={R} className={styles.pista} />
          <g transform="rotate(-90 60 60)">
            {arcos.map((a) => (
              <circle
                key={a.clave}
                cx="60"
                cy="60"
                r={R}
                className={styles.arco}
                stroke={a.color}
                strokeDasharray={`${Math.max(a.largo - 1.5, 0.5)} ${C}`}
                strokeDashoffset={-a.inicio}
                style={{ animationDelay: `${a.i * 90}ms` }}
              />
            ))}
          </g>
        </svg>
        <div className={styles.centro}>
          <span className={`${styles.cifra} cifra`}>{total}</span>
          <span className={styles.centroTexto}>{centro}</span>
        </div>
      </div>
      <ul className={styles.leyenda}>
        {segmentos.map((s) => (
          <li key={s.clave}>
            <Link href={s.href} className={`${styles.item} ${s.valor === 0 ? styles.cero : ""}`}>
              <span className={styles.punto} style={{ background: s.color }} aria-hidden="true" />
              <span className={styles.nombre}>{s.etiqueta}</span>
              <span className={`${styles.valor} cifra`}>{s.valor}</span>
              <span className={styles.pct}>{total > 0 ? `${Math.round((s.valor / total) * 100)}%` : "–"}</span>
            </Link>
          </li>
        ))}
        {pie}
      </ul>
    </div>
  );
}
