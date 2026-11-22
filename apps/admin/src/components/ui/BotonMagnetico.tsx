"use client";

import Link from "next/link";
import { useRef, type PointerEvent, type ReactNode } from "react";
import styles from "./BotonMagnetico.module.css";

const FUERZA = 0.22;
const TOPE = 6;

export default function BotonMagnetico({
  href,
  children,
  className = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLAnchorElement>(null);

  function mover(e: PointerEvent<HTMLAnchorElement>): void {
    if (e.pointerType !== "mouse") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const nodo = ref.current;
    if (!nodo) return;
    const c = nodo.getBoundingClientRect();
    const dx = (e.clientX - (c.left + c.width / 2)) * FUERZA;
    const dy = (e.clientY - (c.top + c.height / 2)) * FUERZA;
    const acota = (v: number) => Math.max(-TOPE, Math.min(TOPE, v));
    nodo.style.setProperty("--iman-x", `${acota(dx)}px`);
    nodo.style.setProperty("--iman-y", `${acota(dy)}px`);
  }

  function soltar(): void {
    ref.current?.style.removeProperty("--iman-x");
    ref.current?.style.removeProperty("--iman-y");
  }

  return (
    <Link
      ref={ref}
      href={href}
      className={`${styles.boton} ${className}`}
      onPointerMove={mover}
      onPointerLeave={soltar}
    >
      {children}
    </Link>
  );
}
