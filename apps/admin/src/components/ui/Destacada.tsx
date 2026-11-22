"use client";

import { useRef, type ElementType, type ReactNode, type PointerEvent } from "react";
import styles from "./Destacada.module.css";

export default function Destacada({
  children,
  className = "",
  as: Etiqueta = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: ElementType;
}) {
  const ref = useRef<HTMLElement>(null);

  function mover(e: PointerEvent<HTMLElement>): void {
    if (e.pointerType !== "mouse") return;
    const nodo = ref.current;
    if (!nodo) return;
    const caja = nodo.getBoundingClientRect();
    nodo.style.setProperty("--luz-x", `${e.clientX - caja.left}px`);
    nodo.style.setProperty("--luz-y", `${e.clientY - caja.top}px`);
  }

  const Contenedor = Etiqueta as ElementType;
  return (
    <Contenedor ref={ref} className={`${styles.destacada} ${className}`} onPointerMove={mover}>
      <span className={styles.haz} aria-hidden="true" />
      <span className={styles.luz} aria-hidden="true" />
      <div className={styles.contenido}>{children}</div>
    </Contenedor>
  );
}
