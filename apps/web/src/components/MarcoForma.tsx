import { useId, type CSSProperties, type ReactNode } from "react";
import estilos from "./MarcoForma.module.css";

// Port a React de `form-frame` (sf-design-stack): una forma con corte curvo,
// dibujada como SVG en linea DETRAS del contenido, con degradado propio y sin
// mask-image. El degradado se dibuja del ancho de la forma y la forma es una
// ventana: `desde` y `hasta` escogen los dos colores. Solo es decoracion
// (aria-hidden); el contenido lleva su propio contraste. Sin animacion.

interface Props {
  children: ReactNode;
  /** Color de arranque del degradado (arriba-izquierda). */
  desde?: string;
  /** Color final (abajo-derecha). */
  hasta?: string;
  className?: string;
  style?: CSSProperties;
  /** Etiqueta del contenedor. */
  as?: "div" | "section" | "header";
}

// Rectangulo de esquinas suaves con un mordisco circular en la esquina
// superior derecha, en unidades de la caja (0..1).
const RUTA =
  "M0.03,0 H0.84 A0.085,0.34 0 0 0 0.935,0.34 A0.065,0.26 0 0 1 1,0.6 V0.96 Q1,1 0.97,1 H0.03 Q0,1 0,0.96 V0.04 Q0,0 0.03,0 Z";

export default function MarcoForma({
  children,
  desde = "var(--clay-cielo-bg)",
  hasta = "var(--clay-cielo-claro)",
  className,
  style,
  as: Etiqueta = "div",
}: Props) {
  const id = useId().replace(/:/g, "");
  return (
    <Etiqueta className={`${estilos.marco} ${className ?? ""}`} style={style}>
      <svg
        className={estilos.forma}
        aria-hidden="true"
        focusable="false"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={`${id}-g`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={desde} />
            <stop offset="1" stopColor={hasta} />
          </linearGradient>
        </defs>
        <path d={RUTA} fill={`url(#${id}-g)`} />
      </svg>
      <div className={estilos.contenido}>{children}</div>
    </Etiqueta>
  );
}
