// Columnas verticales pequeñas (port ligero de `chart-area` de sf-design-stack
// para pocas categorias o los ultimos dias): sin GSAP, cada columna crece una
// vez desde la base con CSS y se apaga con prefers-reduced-motion. Cada columna
// es un item de lista con su texto completo para lectores de pantalla; si trae
// `href` es un enlace de 44 px a su vista filtrada.

import Link from "next/link";
import { proporcion } from "@/lib/graficos";
import styles from "./Columnas.module.css";

export interface Columna {
  clave: string;
  /** Lo que se ve bajo la columna (corto). */
  etiqueta: string;
  /** Lo que se lee y sale en el tooltip ("Primero: 4 listas"). */
  descripcion: string;
  valor: number;
  href?: string;
  /** La columna que importa (hoy, el grado mas cargado): color de marca. */
  realce?: boolean;
}

export default function Columnas({
  columnas,
  etiqueta,
  alto = 56,
}: {
  columnas: readonly Columna[];
  /** aria-label de la lista. */
  etiqueta: string;
  alto?: number;
}) {
  const tope = Math.max(...columnas.map((c) => c.valor), 1);
  return (
    <ul className={styles.columnas} aria-label={etiqueta} style={{ ["--alto" as string]: `${alto}px` }}>
      {columnas.map((c, i) => {
        const cuerpo = (
          <>
            <span className={`${styles.valor} cifra`} aria-hidden="true">
              {c.valor > 0 ? c.valor : ""}
            </span>
            <span className={styles.pista} aria-hidden="true">
              <span
                className={`${styles.relleno} ${c.realce ? styles.realce : ""} ${c.valor === 0 ? styles.cero : ""}`}
                style={{ height: `${c.valor > 0 ? proporcion(c.valor, tope, 8) : 4}%`, animationDelay: `${i * 50}ms` }}
              />
            </span>
            <span className={styles.etiqueta} aria-hidden="true">
              {c.etiqueta}
            </span>
            <span className={styles.soloLector}>{c.descripcion}</span>
          </>
        );
        return (
          <li key={c.clave} title={c.descripcion}>
            {c.href ? (
              <Link href={c.href} className={styles.columna}>
                {cuerpo}
              </Link>
            ) : (
              <span className={styles.columna}>{cuerpo}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
