// Iconos de personaje en clay, para el selector del paso 1.
//
// Son evocaciones ABSTRACTAS —una telaraña, un copo, una corona, un rayo— y no
// arte de personajes con derechos: la franquicia se nombra en texto, el icono
// solo le da un ancla visual amable al niño. Misma casa de estilo que
// `UtilesFlotantes`: gradiente lineal suave, un brillo blanco arriba-izquierda,
// y la sombra difusa la pone el CSS del contenedor. Sin dependencias nuevas:
// todo es SVG inline. Cada componente comparte el mismo viewBox 0 0 48 48 para
// que encajen sin ajustes en la ficha.
//
// El mapa `iconoDe(nombre)` traduce el nombre de catalogo (en minuscula) a su
// pieza; lo que no tenga pieza propia cae en `Generico`, una estrella-sticker
// que sigue leyendose como "personaje" sin mentir sobre cual es.

import type { ComponentType } from "react";

type Props = { className?: string };

// Un id de gradiente unico por icono evita que dos <defs> con el mismo id se
// pisen cuando varios iconos conviven en la misma pagina.
function grad(id: string, desde: string, hasta: string) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stopColor={desde} />
      <stop offset="1" stopColor={hasta} />
    </linearGradient>
  );
}

// Brillo blanco superior: el toque que da el "tacto de plastilina".
function Brillo({ cx, cy, rx, ry }: { cx: number; cy: number; rx: number; ry: number }) {
  return <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="#ffffff" opacity="0.3" />;
}

function Marco({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      {children}
    </svg>
  );
}

function Arana({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-arana", "#ff7a7a", "#d61f2b")}</defs>
      {[0, 45, 90, 135].map((a) => (
        <line
          key={a}
          x1="24"
          y1="24"
          x2={24 + 17 * Math.cos((a * Math.PI) / 180)}
          y2={24 + 17 * Math.sin((a * Math.PI) / 180)}
          stroke="#1e2a4a"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      ))}
      {[0, 45, 90, 135].map((a) => (
        <line
          key={`-${a}`}
          x1="24"
          y1="24"
          x2={24 - 17 * Math.cos((a * Math.PI) / 180)}
          y2={24 - 17 * Math.sin((a * Math.PI) / 180)}
          stroke="#1e2a4a"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      ))}
      <circle cx="24" cy="24" r="11" fill="url(#ic-arana)" />
      <Brillo cx={20} cy={19} rx={5} ry={3} />
    </Marco>
  );
}

function Copo({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-copo", "#bfe8ff", "#4aa3e0")}</defs>
      <g stroke="url(#ic-copo)" strokeWidth="3.2" strokeLinecap="round">
        {[0, 60, 120].map((a) => (
          <line
            key={a}
            x1={24 - 16 * Math.cos((a * Math.PI) / 180)}
            y1={24 - 16 * Math.sin((a * Math.PI) / 180)}
            x2={24 + 16 * Math.cos((a * Math.PI) / 180)}
            y2={24 + 16 * Math.sin((a * Math.PI) / 180)}
          />
        ))}
      </g>
      <g stroke="url(#ic-copo)" strokeWidth="2.6" strokeLinecap="round">
        {[0, 60, 120, 180, 240, 300].map((a) => {
          const bx = 24 + 9 * Math.cos((a * Math.PI) / 180);
          const by = 24 + 9 * Math.sin((a * Math.PI) / 180);
          return (
            <line
              key={a}
              x1={bx}
              y1={by}
              x2={bx + 5 * Math.cos(((a + 40) * Math.PI) / 180)}
              y2={by + 5 * Math.sin(((a + 40) * Math.PI) / 180)}
            />
          );
        })}
      </g>
      <circle cx="24" cy="24" r="3.4" fill="#ffffff" />
    </Marco>
  );
}

function Corona({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-corona", "#ffdd6b", "#e0a92b")}</defs>
      <path
        d="M9 18 L16 27 L24 15 L32 27 L39 18 L36 36 L12 36 Z"
        fill="url(#ic-corona)"
      />
      <rect x="11" y="35" width="26" height="5" rx="2.5" fill="#e0a92b" />
      <circle cx="9" cy="18" r="3" fill="#ff8fb0" />
      <circle cx="39" cy="18" r="3" fill="#ff8fb0" />
      <circle cx="24" cy="15" r="3" fill="#ff8fb0" />
      <Brillo cx={19} cy={22} rx={5} ry={2.5} />
    </Marco>
  );
}

function Rayo({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-rayo", "#ffe36b", "#f0b429")}</defs>
      <path d="M27 6 L13 27 L22 27 L20 42 L36 20 L26 20 Z" fill="url(#ic-rayo)" />
      <path d="M27 6 L13 27 L22 27 Z" fill="#ffffff" opacity="0.28" />
    </Marco>
  );
}

function Pata({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-pata", "#9bd6b0", "#3fbf6b")}</defs>
      <ellipse cx="24" cy="30" rx="11" ry="9" fill="url(#ic-pata)" />
      <circle cx="14" cy="18" r="4.5" fill="url(#ic-pata)" />
      <circle cx="24" cy="14" r="4.5" fill="url(#ic-pata)" />
      <circle cx="34" cy="18" r="4.5" fill="url(#ic-pata)" />
      <Brillo cx={21} cy={27} rx={4} ry={2.5} />
    </Marco>
  );
}

function EstrellaIcono({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-est", "#ffdd6b", "#e0a92b")}</defs>
      <path
        d="M24 6 L28.5 18 L41 18.6 L31 26.5 L34.5 39 L24 31.5 L13.5 39 L17 26.5 L7 18.6 L19.5 18 Z"
        fill="url(#ic-est)"
      />
      <path d="M24 6 L28.5 18 L41 18.6 L31 26.5 Z" fill="#ffffff" opacity="0.26" />
    </Marco>
  );
}

function Carro({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-carro", "#ff7a7a", "#d61f2b")}</defs>
      <path d="M8 30 L13 21 L33 21 L40 30 L40 34 L8 34 Z" fill="url(#ic-carro)" />
      <path d="M16 22 L31 22 L35 29 L13 29 Z" fill="#bfe8ff" />
      <circle cx="16" cy="35" r="4.5" fill="#1e2a4a" />
      <circle cx="33" cy="35" r="4.5" fill="#1e2a4a" />
      <Brillo cx={18} cy={26} rx={6} ry={2} />
    </Marco>
  );
}

function Unicornio({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-uni", "#ffc2e0", "#db2777")}</defs>
      {/* cuerno */}
      <path d="M24 5 L28 20 L20 20 Z" fill="url(#ic-uni)" />
      <path d="M24 5 L26 12 L22 12 Z" fill="#ffffff" opacity="0.4" />
      {/* cabeza */}
      <ellipse cx="24" cy="31" rx="12" ry="10" fill="url(#ic-uni)" />
      <circle cx="20" cy="30" r="1.8" fill="#1e2a4a" />
      <circle cx="28" cy="30" r="1.8" fill="#1e2a4a" />
      <Brillo cx={20} cy={26} rx={5} ry={2.5} />
    </Marco>
  );
}

function Dino({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-dino", "#9bd6b0", "#3fbf6b")}</defs>
      <path
        d="M10 34 Q10 20 24 20 Q34 20 36 12 Q40 20 34 26 Q40 28 40 34 Z"
        fill="url(#ic-dino)"
      />
      <circle cx="31" cy="24" r="1.8" fill="#1e2a4a" />
      <path d="M14 20 L18 15 L20 20 Z M20 19 L24 14 L27 19 Z" fill="#2f8f52" />
      <Brillo cx={20} cy={26} rx={5} ry={2.5} />
    </Marco>
  );
}

function Balon({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-balon", "#ffffff", "#dfe6f0")}</defs>
      <circle cx="24" cy="24" r="16" fill="url(#ic-balon)" />
      <path
        d="M24 15 L31 20 L28 29 L20 29 L17 20 Z"
        fill="#1e2a4a"
      />
      <circle cx="24" cy="24" r="16" fill="none" stroke="#c9d3e0" strokeWidth="1.5" />
      <Brillo cx={19} cy={18} rx={5} ry={3} />
    </Marco>
  );
}

function Corazon({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-corazon", "#ffc2e0", "#db2777")}</defs>
      <path
        d="M24 39 C6 27 12 12 24 20 C36 12 42 27 24 39 Z"
        fill="url(#ic-corazon)"
      />
      <Brillo cx={18} cy={20} rx={4} ry={3} />
    </Marco>
  );
}

function Robot({ className }: Props) {
  return (
    <Marco className={className}>
      <defs>{grad("ic-robot", "#8fd3f4", "#2f8fd6")}</defs>
      <rect x="12" y="14" width="24" height="22" rx="7" fill="url(#ic-robot)" />
      <rect x="21" y="8" width="6" height="6" rx="3" fill="#c9d3e0" />
      <circle cx="19" cy="24" r="3" fill="#ffffff" />
      <circle cx="29" cy="24" r="3" fill="#ffffff" />
      <rect x="18" y="30" width="12" height="3" rx="1.5" fill="#1e2a4a" />
      <Brillo cx={18} cy={19} rx={4} ry={2} />
    </Marco>
  );
}

// Generico: estrella-sticker para cualquier franquicia sin pieza propia. No
// finge ser el personaje; solo dice "esto es un gusto que buscaremos".
const Generico = EstrellaIcono;

// Mapa nombre-de-catalogo (minuscula) -> pieza. Las 7 franquicias completas de
// hoy (bluey, cars, frozen, minnie, paw patrol, spiderman, stitch) tienen su
// ancla; el resto que llegue completo cae en el generico hasta que se le dibuje
// una pieza. Las llaves extra (barbie, sonic, dinosaurios...) cubren gustos
// frecuentes del campo libre para que el chip elegido no se vea desnudo.
const MAPA: Record<string, ComponentType<Props>> = {
  spiderman: Arana,
  frozen: Copo,
  minnie: Corazon,
  "paw patrol": Pata,
  bluey: Pata,
  cars: Carro,
  stitch: EstrellaIcono,
  barbie: Corazon,
  "hot wheels": Carro,
  sonic: Rayo,
  "harry potter": Rayo,
  kitty: Corazon,
  dinosaurios: Dino,
  futbol: Balon,
  "fútbol": Balon,
  unicornios: Unicornio,
  unicornio: Unicornio,
  minecraft: Robot,
  princesas: Corona,
  princesa: Corona,
};

/** Devuelve el componente de icono para un nombre de personaje. */
export function iconoDe(nombre: string): ComponentType<Props> {
  return MAPA[nombre.trim().toLowerCase()] ?? Generico;
}
