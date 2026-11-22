"use client";

import { useRef, type ElementType, type ReactNode } from "react";
import { useGSAP, entrada, entradaEnCascada, revelarEnScroll } from "@tukit/contrato/motion";

interface Props {
  children: ReactNode;
  modo?: "una" | "cascada" | "scroll";
  retraso?: number;
  cadaUno?: number;
  className?: string;
  as?: ElementType;
}

export default function Revelar({
  children,
  modo = "una",
  retraso = 0,
  cadaUno,
  className,
  as: Etiqueta = "div",
}: Props) {
  const ref = useRef<HTMLElement>(null);
  const Contenedor = Etiqueta as ElementType;

  useGSAP(
    () => {
      const nodo = ref.current;
      if (!nodo) return;
      if (modo === "una") {
        entrada(nodo, { retraso });
      } else if (modo === "cascada") {
        entradaEnCascada(Array.from(nodo.children), { retraso, cadaUno });
      } else {
        revelarEnScroll(Array.from(nodo.children), { cadaUno });
      }
    },
    { scope: ref },
  );

  return (
    <Contenedor ref={ref} className={className}>
      {children}
    </Contenedor>
  );
}
