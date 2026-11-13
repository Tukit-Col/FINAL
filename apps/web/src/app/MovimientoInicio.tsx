"use client";

// Piezas de movimiento de la portada, portadas de sf-design-stack
// (spotlight-card, marker-title, text-reveal, contador) con los tokens de TUKIT.
// Sin librerias: CSS + IntersectionObserver + una escritura de variable CSS.
//
// Regla comun: el estado FINAL es el que sirve el servidor y el que ve quien
// pide menos movimiento. Solo despues de montar, y solo si el sistema permite
// movimiento, se pone el estado "pendiente" y se dispara al entrar en pantalla.
// Asi, sin JS o con `prefers-reduced-motion`, el contenido nunca queda oculto.

import {
  useEffect,
  useRef,
  useState,
  type ElementType,
  type PointerEvent,
  type ReactNode,
} from "react";
import styles from "./MovimientoInicio.module.css";

function sinMovimiento(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Devuelve [ref, fase]: "final" (servidor / movimiento reducido), "pendiente"
 *  (montado, aun fuera de pantalla) y "dentro" (ya se vio, una sola vez). */
function useAlEntrar<T extends HTMLElement>(umbral = 0.35) {
  const ref = useRef<T>(null);
  const [fase, setFase] = useState<"final" | "pendiente" | "dentro">("final");

  useEffect(() => {
    const nodo = ref.current;
    if (!nodo || sinMovimiento() || typeof IntersectionObserver === "undefined") return;
    const caja = nodo.getBoundingClientRect();
    // Ya esta a la vista al montar: entra de una vez en lugar de parpadear.
    const visible = caja.top < window.innerHeight * 0.9 && caja.bottom > 0;
    setFase(visible ? "dentro" : "pendiente");
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setFase("dentro");
          obs.disconnect();
        }
      },
      { threshold: umbral, rootMargin: "0px 0px -6% 0px" },
    );
    obs.observe(nodo);
    return () => obs.disconnect();
  }, [umbral]);

  return [ref, fase] as const;
}

/* ------------------------------------------------------------ Foco (spotlight) */

/** Tarjeta con una luz que sigue al cursor (spotlight-card). Escribe --x/--y en
 *  el nodo directamente: no re-renderiza nada al mover el puntero. */
export function Foco({
  children,
  className = "",
  as: Etiqueta = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: ElementType;
}) {
  function mover(e: PointerEvent<HTMLElement>) {
    const caja = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--x", `${e.clientX - caja.left}px`);
    e.currentTarget.style.setProperty("--y", `${e.clientY - caja.top}px`);
  }
  const E = Etiqueta as ElementType;
  return (
    <E className={`${styles.foco} ${className}`} onPointerMove={mover}>
      {children}
    </E>
  );
}

/* --------------------------------------------------------------- Marcador */

/** Marcador que se dibuja bajo una frase (marker-title). Es un fondo CSS con
 *  `box-decoration-break: clone`: continuo de extremo a extremo y, si la frase
 *  se parte en dos lineas, cada linea lleva su propio trazo completo. */
export function Marcador({ children }: { children: ReactNode }) {
  const [ref, fase] = useAlEntrar<HTMLSpanElement>(0.4);
  return (
    <span ref={ref} className={styles.marcador} data-fase={fase}>
      {children}
    </span>
  );
}

/* --------------------------------------------------------------- Palabras */

/** Titulo que entra palabra por palabra (text-reveal). El texto completo sigue
 *  en el DOM como una sola cadena accesible. */
export function Palabras({ texto }: { texto: string }) {
  const [ref, fase] = useAlEntrar<HTMLSpanElement>(0.6);
  const palabras = texto.split(" ");
  return (
    <span ref={ref} className={styles.palabras} data-fase={fase} aria-label={texto}>
      {palabras.map((p, i) => (
        <span key={i} className={styles.palabra} aria-hidden="true" style={{ ["--i" as string]: i }}>
          {p}
          {i < palabras.length - 1 ? " " : ""}
        </span>
      ))}
    </span>
  );
}

/* --------------------------------------------------------------- Contador */

/** Cifra que sube de 0 al valor cuando entra en pantalla. El servidor sirve el
 *  valor final; el ancho se reserva con `tabular-nums` para que no salte. */
export function Contador({
  valor,
  sufijo = "",
  duracion = 1400,
}: {
  valor: number;
  sufijo?: string;
  duracion?: number;
}) {
  const [ref, fase] = useAlEntrar<HTMLSpanElement>(0.6);
  const [n, setN] = useState(valor);

  useEffect(() => {
    let raf = 0;
    if (fase === "pendiente") {
      raf = requestAnimationFrame(() => setN(0));
      return () => cancelAnimationFrame(raf);
    }
    if (fase !== "dentro") return;
    const t0 = performance.now();
    const paso = (t: number) => {
      const p = Math.min(1, (t - t0) / duracion);
      setN(Math.round(valor * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [fase, valor, duracion]);

  return (
    <span ref={ref} className={styles.contador}>
      {n}
      {sufijo}
    </span>
  );
}
