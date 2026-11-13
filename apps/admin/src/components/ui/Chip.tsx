// Chip de filtro: un enlace con tres estados (normal, "hay algo", activo).
// Objetivo tactil de 44 px; el estado activo se anuncia con aria-current.

import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./ui.module.css";

export function Chips({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <nav className={styles.chips} aria-label={etiqueta}>
      {children}
    </nav>
  );
}

export default function Chip({
  href,
  activo = false,
  hay = false,
  children,
}: {
  href: string;
  activo?: boolean;
  hay?: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`${styles.chip} ${activo ? styles.activo : ""} ${hay && !activo ? styles.hay : ""}`}
      aria-current={activo ? "true" : undefined}
    >
      {children}
    </Link>
  );
}
