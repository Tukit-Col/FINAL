"use client";

// Tarjeta destacada: port de `spotlight-card` + `border-beam` de sf-design-stack
// a React/CSS. Se usa en UNA sola tarjeta por vista, la de mayor urgencia: el
// haz que recorre el borde dice "empieza por aqui" (jerarquia) y la luz que
// sigue al puntero es feedback de que es interactiva. Sin GSAP: el haz es un
// conic-gradient animado por @property y la luz son dos variables CSS.
// prefers-reduced-motion y puntero tactil: sin haz giratorio ni luz.

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
