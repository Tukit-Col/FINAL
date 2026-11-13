"use client";

// Envoltorio de cliente para animar entradas sin convertir cada pantalla en un
// componente de cliente. Las páginas siguen siendo Server Components que leen
// del origen; solo la cáscara que anima es cliente. Todo delega en el helper de
// motion del contrato, que ya respeta `prefers-reduced-motion`.

import { useRef, type ElementType, type ReactNode } from "react";
import { useGSAP, entradaEnCascada, revelarAlEntrar } from "@tukit/contrato/motion";

interface Props {
  children: ReactNode;
  /** `una` entra el bloque entero; `cascada` escalona los hijos directos;
   *  `scroll` revela cada hijo cuando entra en pantalla. */
  modo?: "una" | "cascada" | "scroll";
  retraso?: number;
  cadaUno?: number;
  className?: string;
  /** Etiqueta semántica del contenedor (section, ul, div…). */
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
        // Bloques de seccion: animan al entrar en vista, no al montar (si no,
        // los de abajo gastaban la animacion fuera de pantalla).
        return revelarAlEntrar(nodo, { retraso, y: 22 });
      } else if (modo === "cascada") {
        entradaEnCascada(Array.from(nodo.children), { retraso, cadaUno });
      } else {
        return revelarAlEntrar(Array.from(nodo.children), { cadaUno });
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
