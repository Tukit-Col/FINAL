"use client";

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

function useAlEntrar<T extends HTMLElement>(umbral = 0.35) {
  const ref = useRef<T>(null);
  const [fase, setFase] = useState<"final" | "pendiente" | "dentro">("final");

  useEffect(() => {
    const nodo = ref.current;
    if (!nodo || sinMovimiento() || typeof IntersectionObserver === "undefined") return;
    const caja = nodo.getBoundingClientRect();
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

export function Marcador({ children }: { children: ReactNode }) {
  const [ref, fase] = useAlEntrar<HTMLSpanElement>(0.4);
  return (
    <span ref={ref} className={styles.marcador} data-fase={fase}>
      {children}
    </span>
  );
}

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
