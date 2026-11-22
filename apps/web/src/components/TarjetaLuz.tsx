"use client";

import { useRef, type ReactNode } from "react";
import estilos from "./TarjetaLuz.module.css";

interface Props {
  children: ReactNode;
  className?: string;
  "aria-live"?: "polite" | "off";
}

export default function TarjetaLuz({ children, className, "aria-live": ariaLive }: Props) {
  const ref = useRef<HTMLElement>(null);

  function mover(e: React.PointerEvent<HTMLElement>) {
    if (e.pointerType === "touch") return;
    const nodo = ref.current;
    if (!nodo) return;
    const caja = nodo.getBoundingClientRect();
    nodo.style.setProperty("--luz-x", `${((e.clientX - caja.left) / caja.width) * 100}%`);
    nodo.style.setProperty("--luz-y", `${((e.clientY - caja.top) / caja.height) * 100}%`);
    nodo.dataset["siguiendo"] = "1";
  }

  function soltar() {
    const nodo = ref.current;
    if (!nodo) return;
    delete nodo.dataset["siguiendo"];
    nodo.style.removeProperty("--luz-x");
    nodo.style.removeProperty("--luz-y");
  }

  return (
    <section
      ref={ref}
      className={`${estilos.tarjeta} ${className ?? ""}`}
      aria-live={ariaLive}
      onPointerMove={mover}
      onPointerLeave={soltar}
    >
      <span className={estilos.luz} aria-hidden="true" />
      {children}
    </section>
  );
}
