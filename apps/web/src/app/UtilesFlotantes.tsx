// Útiles escolares en clay, flotando alrededor del titular del héroe.
//
// Son ilustraciones DECORATIVAS (aria-hidden): construidas a mano en SVG con la
// paleta del logo, para que el héroe tenga el mismo peso visual que una landing
// de startup sin depender de imágenes raster pesadas ni de una librería externa.
// El "tacto de plastilina" sale de tres cosas: gradientes suaves, un brillo
// blanco arriba-izquierda, y la sombra difusa (filter: drop-shadow) que pone el
// CSS en el envoltorio. El leve flotar también vive en el CSS y el bloque global
// de `prefers-reduced-motion` lo neutraliza sin que este archivo sepa nada.
//
// Es un Server Component normal (solo markup); no necesita "use client".

import styles from "./UtilesFlotantes.module.css";

// La estrella del logo, reutilizada en varias piezas.
function Estrella({ x, y, tam, color }: { x: number; y: number; tam: number; color: string }) {
  const p = (n: number) => (n / 24) * tam;
  return (
    <path
      transform={`translate(${x} ${y})`}
      d={`M${p(12)} ${p(2)}l${p(2.9)} ${p(6)} ${p(6.5)} ${p(0.6)}-${p(4.9)} ${p(4.3)} ${p(1.5)} ${p(6.4)}-${p(6)}-${p(3.4)}-${p(6)} ${p(3.4)} ${p(1.5)}-${p(6.4)}-${p(4.9)}-${p(4.3)} ${p(6.5)}-${p(0.6)}z`}
      fill={color}
    />
  );
}

/** Librito con estrella — el motivo del logo, la pieza principal. */
function Libro() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-libro" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#5eb0e8" />
          <stop offset="1" stopColor="#1e40af" />
        </linearGradient>
        <linearGradient id="uf-libro-b" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#4aa0dd" />
          <stop offset="1" stopColor="#1b3a9e" />
        </linearGradient>
      </defs>
      <rect x="14" y="26" width="40" height="62" rx="10" fill="url(#uf-libro)" />
      <rect x="56" y="26" width="40" height="62" rx="10" fill="url(#uf-libro-b)" />
      <rect x="20" y="32" width="28" height="50" rx="5" fill="#ffffff" />
      <rect x="62" y="32" width="28" height="50" rx="5" fill="#eef3fb" />
      <Estrella x={40} y={38} tam={30} color="#f5c542" />
      <ellipse cx="30" cy="36" rx="14" ry="6" fill="#ffffff" opacity="0.35" />
    </svg>
  );
}

/** Lápiz amarillo con punta y goma. */
function Lapiz() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-lapiz" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd75e" />
          <stop offset="1" stopColor="#f0b429" />
        </linearGradient>
      </defs>
      <g transform="rotate(-38 55 55)">
        <rect x="30" y="20" width="50" height="20" rx="6" fill="url(#uf-lapiz)" />
        {/* goma */}
        <rect x="24" y="20" width="12" height="20" rx="6" fill="#f6a5c0" />
        <rect x="34" y="20" width="4" height="20" fill="#c9d3e0" />
        {/* punta */}
        <path d="M80 20 L98 30 L80 40 Z" fill="#f2d3a7" />
        <path d="M92 27 L98 30 L92 33 Z" fill="#2b2b2b" />
        <rect x="30" y="24" width="50" height="4" rx="2" fill="#ffffff" opacity="0.5" />
      </g>
    </svg>
  );
}

/** Crayón cielo con envoltura. */
function Crayon() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-crayon" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#6fc0f0" />
          <stop offset="1" stopColor="#2f8fd6" />
        </linearGradient>
      </defs>
      <g transform="rotate(24 55 55)">
        <rect x="38" y="24" width="34" height="62" rx="12" fill="url(#uf-crayon)" />
        {/* punta */}
        <path d="M38 30 Q55 6 72 30 Z" fill="#4aa3e0" />
        {/* etiquetas */}
        <rect x="38" y="42" width="34" height="7" fill="#ffffff" opacity="0.85" />
        <rect x="38" y="62" width="34" height="7" fill="#ffffff" opacity="0.85" />
        <rect x="44" y="30" width="6" height="52" rx="3" fill="#ffffff" opacity="0.4" />
      </g>
    </svg>
  );
}

/** Cuaderno con espiral. */
function Cuaderno() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-cuad" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" stopColor="#ff8fb0" />
          <stop offset="1" stopColor="#db2777" />
        </linearGradient>
      </defs>
      <rect x="24" y="22" width="62" height="70" rx="10" fill="url(#uf-cuad)" />
      <rect x="40" y="22" width="46" height="70" rx="8" fill="#ffffff" />
      <rect x="48" y="40" width="30" height="5" rx="2.5" fill="#e6eaf2" />
      <rect x="48" y="54" width="30" height="5" rx="2.5" fill="#e6eaf2" />
      <rect x="48" y="68" width="20" height="5" rx="2.5" fill="#e6eaf2" />
      {/* espiral */}
      {[30, 44, 58, 72, 86].map((cy) => (
        <rect key={cy} x="34" y={cy - 3} width="14" height="6" rx="3" fill="#c9d3e0" />
      ))}
    </svg>
  );
}

/** Regla. */
function Regla() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-regla" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#8fd3f4" />
          <stop offset="1" stopColor="#4aa3e0" />
        </linearGradient>
      </defs>
      <g transform="rotate(-18 55 55)">
        <rect x="10" y="42" width="90" height="26" rx="8" fill="url(#uf-regla)" />
        {[22, 34, 46, 58, 70, 82].map((x, i) => (
          <rect key={x} x={x} y="42" width="3" height={i % 2 ? 8 : 13} rx="1.5" fill="#ffffff" opacity="0.85" />
        ))}
        <rect x="14" y="46" width="82" height="4" rx="2" fill="#ffffff" opacity="0.4" />
      </g>
    </svg>
  );
}

/** Borrador dos tonos. */
function Borrador() {
  return (
    <svg viewBox="0 0 110 110" className={styles.svg} aria-hidden="true">
      <defs>
        <linearGradient id="uf-bor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a5e3b8" />
          <stop offset="1" stopColor="#3fbf6b" />
        </linearGradient>
      </defs>
      <g transform="rotate(12 55 55)">
        <rect x="26" y="40" width="58" height="30" rx="9" fill="url(#uf-bor)" />
        <rect x="26" y="40" width="58" height="13" rx="9" fill="#ffffff" opacity="0.9" />
        <rect x="32" y="44" width="46" height="4" rx="2" fill="#e6eaf2" />
      </g>
    </svg>
  );
}

// Cada pieza con su clase de posición + flotar. `data-flota` deja al CSS variar
// el ritmo del flotar por pieza.
const PIEZAS = [
  { Comp: Lapiz, clase: "posLapiz", flota: "a" },
  { Comp: Cuaderno, clase: "posCuaderno", flota: "b" },
  { Comp: Libro, clase: "posLibro", flota: "c" },
  { Comp: Regla, clase: "posRegla", flota: "a" },
  { Comp: Crayon, clase: "posCrayon", flota: "b" },
  { Comp: Borrador, clase: "posBorrador", flota: "c" },
] as const;

export default function UtilesFlotantes() {
  return (
    <div className={styles.capa} aria-hidden="true">
      {PIEZAS.map(({ Comp, clase, flota }, i) => (
        <span key={i} className={`${styles.pieza} ${styles[clase]}`} data-flota={flota}>
          <Comp />
        </span>
      ))}
    </div>
  );
}
