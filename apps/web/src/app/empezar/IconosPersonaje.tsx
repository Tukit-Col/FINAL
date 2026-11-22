import type { ComponentType, ReactNode } from "react";

type Props = { className?: string };

function grad(id: string, desde: string, hasta: string) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stopColor={desde} />
      <stop offset="1" stopColor={hasta} />
    </linearGradient>
  );
}

function Marco({
  children,
  className,
  id,
  desde,
  hasta,
}: {
  children: ReactNode;
  className?: string;
  id: string;
  desde: string;
  hasta: string;
}) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <defs>{grad(`tile-${id}`, desde, hasta)}</defs>
      <circle cx="24" cy="24" r="22" fill={`url(#tile-${id})`} />
      <ellipse cx="18" cy="15" rx="11" ry="6" fill="#ffffff" opacity="0.18" />
      {children}
    </svg>
  );
}

function Arana({ className }: Props) {
  return (
    <Marco className={className} id="arana" desde="#ff5a5a" hasta="#c81420">
      <g stroke="#7c0d16" strokeWidth="1" opacity="0.65" fill="none">
        {[10, 24, 38].map((y) => (
          <line key={y} x1="8" y1={y} x2="40" y2={y} />
        ))}
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1="24" y1="24" x2={24 + 20 * Math.cos((i * 72 - 90) * Math.PI / 180)} y2={24 + 20 * Math.sin((i * 72 - 90) * Math.PI / 180)} />
        ))}
      </g>
      <path d="M14 20 Q14 15 21 17 Q22 22 16 24 Q13 23 14 20 Z" fill="#fff" stroke="#12203f" strokeWidth="1.4" />
      <path d="M34 20 Q34 15 27 17 Q26 22 32 24 Q35 23 34 20 Z" fill="#fff" stroke="#12203f" strokeWidth="1.4" />
    </Marco>
  );
}

function Copo({ className }: Props) {
  return (
    <Marco className={className} id="copo" desde="#dff2ff" hasta="#7cc0ee">
      <g stroke="#2f7bb3" strokeWidth="2.4" strokeLinecap="round">
        {[0, 60, 120].map((a) => (
          <line
            key={a}
            x1={24 - 14 * Math.cos((a * Math.PI) / 180)}
            y1={24 - 14 * Math.sin((a * Math.PI) / 180)}
            x2={24 + 14 * Math.cos((a * Math.PI) / 180)}
            y2={24 + 14 * Math.sin((a * Math.PI) / 180)}
          />
        ))}
      </g>
      <g stroke="#2f7bb3" strokeWidth="2" strokeLinecap="round">
        {[0, 60, 120, 180, 240, 300].map((a) => {
          const bx = 24 + 8 * Math.cos((a * Math.PI) / 180);
          const by = 24 + 8 * Math.sin((a * Math.PI) / 180);
          return (
            <line
              key={a}
              x1={bx}
              y1={by}
              x2={bx + 4.5 * Math.cos(((a + 40) * Math.PI) / 180)}
              y2={by + 4.5 * Math.sin(((a + 40) * Math.PI) / 180)}
            />
          );
        })}
      </g>
      <circle cx="24" cy="24" r="3" fill="#fff" />
    </Marco>
  );
}

function Mono({ className }: Props) {
  return (
    <Marco className={className} id="mono" desde="#ff64a6" hasta="#e01e63">
      <path d="M24 24 L11 15 Q7 22 11 33 L24 24 Z" fill="#ff3d8b" stroke="#b01050" strokeWidth="1.2" />
      <path d="M24 24 L37 15 Q41 22 37 33 L24 24 Z" fill="#ff3d8b" stroke="#b01050" strokeWidth="1.2" />
      <circle cx="24" cy="24" r="4.5" fill="#d40f57" />
      <circle cx="15" cy="20" r="1.5" fill="#fff" />
      <circle cx="15" cy="28" r="1.5" fill="#fff" />
      <circle cx="33" cy="20" r="1.5" fill="#fff" />
      <circle cx="33" cy="28" r="1.5" fill="#fff" />
    </Marco>
  );
}

function Pata({ className }: Props) {
  return (
    <Marco className={className} id="pata" desde="#ffd24d" hasta="#e8890f">
      <ellipse cx="24" cy="30" rx="9" ry="7.5" fill="#fff" />
      <circle cx="14.5" cy="20" r="3.6" fill="#fff" />
      <circle cx="24" cy="16.5" r="3.6" fill="#fff" />
      <circle cx="33.5" cy="20" r="3.6" fill="#fff" />
    </Marco>
  );
}

function Perro({ className }: Props) {
  return (
    <Marco className={className} id="perro" desde="#5ab0f2" hasta="#1f6fc4">
      <path d="M13 16 Q10 26 14 30 L16 22 Z" fill="#155a9e" />
      <path d="M35 16 Q38 26 34 30 L32 22 Z" fill="#155a9e" />
      <ellipse cx="24" cy="26" rx="12" ry="11" fill="#7cc0f5" />
      <ellipse cx="24" cy="31" rx="7" ry="5.5" fill="#fff" />
      <circle cx="19" cy="24" r="1.9" fill="#12203f" />
      <circle cx="29" cy="24" r="1.9" fill="#12203f" />
      <ellipse cx="24" cy="29" rx="2.2" ry="1.6" fill="#12203f" />
    </Marco>
  );
}

function Carro({ className }: Props) {
  return (
    <Marco className={className} id="carro" desde="#ff5a4d" hasta="#c81420">
      <path d="M9 30 L14 22 Q17 19 24 19 L31 19 L37 25 L39 30 Z" fill="#ff4a3c" stroke="#8f0f16" strokeWidth="1" />
      <path d="M18 22 Q20 20 26 20 L30 24 L17 24 Z" fill="#bfe8ff" />
      <path d="M14 30 L18 24 L16 30 Z" fill="#ffd24d" />
      <circle cx="17" cy="31" r="4" fill="#12203f" />
      <circle cx="33" cy="31" r="4" fill="#12203f" />
      <circle cx="17" cy="31" r="1.6" fill="#c9d3e0" />
      <circle cx="33" cy="31" r="1.6" fill="#c9d3e0" />
    </Marco>
  );
}

function Alien({ className }: Props) {
  return (
    <Marco className={className} id="alien" desde="#5aa0ea" hasta="#1f5fc0">
      <path d="M15 20 Q6 9 6 19 Q7 27 16 25 Z" fill="#ff9ecb" stroke="#e86fa8" strokeWidth="1" />
      <path d="M33 20 Q42 9 42 19 Q41 27 32 25 Z" fill="#ff9ecb" stroke="#e86fa8" strokeWidth="1" />
      <path d="M22 12 Q24 8 26 12 Z" fill="#3f7fd0" />
      <ellipse cx="24" cy="27" rx="12.5" ry="11.5" fill="#6fb0f2" />
      <ellipse cx="19.5" cy="25" rx="3.8" ry="4.4" fill="#12203f" />
      <ellipse cx="28.5" cy="25" rx="3.8" ry="4.4" fill="#12203f" />
      <circle cx="21" cy="23.4" r="1.3" fill="#fff" />
      <circle cx="30" cy="23.4" r="1.3" fill="#fff" />
      <ellipse cx="24" cy="30.5" rx="2.6" ry="2" fill="#1f3a6b" />
      <path d="M20 33.5 Q24 37 28 33.5" stroke="#1f3a6b" strokeWidth="1.4" fill="none" strokeLinecap="round" />
    </Marco>
  );
}

function Corona({ className }: Props) {
  return (
    <Marco className={className} id="corona" desde="#ffe07a" hasta="#e0a92b">
      <path d="M12 30 L15 20 L20 26 L24 17 L28 26 L33 20 L36 30 Z" fill="#fff2c2" stroke="#c8901f" strokeWidth="1" />
      <rect x="13" y="30" width="22" height="4" rx="2" fill="#e0a92b" />
      <circle cx="24" cy="16" r="2.2" fill="#ff8fb0" />
    </Marco>
  );
}

function Rayo({ className }: Props) {
  return (
    <Marco className={className} id="rayo" desde="#ffe36b" hasta="#f0b429">
      <path d="M27 10 L15 26 L22 26 L20 38 L33 21 L25 21 Z" fill="#fff6d6" stroke="#d99a0f" strokeWidth="1" />
    </Marco>
  );
}

function Unicornio({ className }: Props) {
  return (
    <Marco className={className} id="uni" desde="#ffc2e0" hasta="#db2777">
      <path d="M24 8 L27 19 L21 19 Z" fill="#ffe07a" stroke="#e0a92b" strokeWidth="0.8" />
      <ellipse cx="24" cy="29" rx="11" ry="9.5" fill="#ffd6ea" />
      <circle cx="20" cy="28" r="1.7" fill="#12203f" />
      <circle cx="28" cy="28" r="1.7" fill="#12203f" />
      <path d="M32 22 Q37 24 35 30" stroke="#a5f3d0" strokeWidth="2.4" fill="none" strokeLinecap="round" />
    </Marco>
  );
}

function Dino({ className }: Props) {
  return (
    <Marco className={className} id="dino" desde="#9be0a8" hasta="#2f9f52">
      <path d="M12 33 Q11 20 24 20 Q33 20 35 13 Q39 20 33 26 Q39 28 38 33 Z" fill="#bff0c8" stroke="#2f8f52" strokeWidth="1" />
      <circle cx="30" cy="23" r="1.7" fill="#12203f" />
      <path d="M16 20 L19 15 L21 20 Z M22 19 L25 15 L27 19 Z" fill="#2f8f52" />
    </Marco>
  );
}

function Balon({ className }: Props) {
  return (
    <Marco className={className} id="balon" desde="#ffffff" hasta="#dfe6f0">
      <circle cx="24" cy="24" r="14" fill="#fff" stroke="#c9d3e0" strokeWidth="1.4" />
      <path d="M24 16 L30 20.5 L27.5 28 L20.5 28 L18 20.5 Z" fill="#12203f" />
    </Marco>
  );
}

function Corazon({ className }: Props) {
  return (
    <Marco className={className} id="corazon" desde="#ffc2e0" hasta="#db2777">
      <path d="M24 35 C10 26 15 15 24 22 C33 15 38 26 24 35 Z" fill="#ff7ab0" stroke="#c01a63" strokeWidth="1" />
    </Marco>
  );
}

function Robot({ className }: Props) {
  return (
    <Marco className={className} id="robot" desde="#8fd3f4" hasta="#2f8fd6">
      <rect x="14" y="16" width="20" height="18" rx="6" fill="#bfe8ff" stroke="#2f7bb3" strokeWidth="1" />
      <rect x="22" y="10" width="4" height="6" rx="2" fill="#c9d3e0" />
      <circle cx="20" cy="24" r="2.6" fill="#12203f" />
      <circle cx="28" cy="24" r="2.6" fill="#12203f" />
      <rect x="19" y="29" width="10" height="2.4" rx="1.2" fill="#2f7bb3" />
    </Marco>
  );
}

function EstrellaIcono({ className }: Props) {
  return (
    <Marco className={className} id="est" desde="#ffe07a" hasta="#e0a92b">
      <path
        d="M24 11 L27.5 20 L37 20.5 L29.5 26.5 L32 36 L24 30.5 L16 36 L18.5 26.5 L11 20.5 L20.5 20 Z"
        fill="#fff2c2"
        stroke="#c8901f"
        strokeWidth="1"
      />
    </Marco>
  );
}

const Generico = EstrellaIcono;

const MAPA: Record<string, ComponentType<Props>> = {
  spiderman: Arana,
  frozen: Copo,
  minnie: Mono,
  "paw patrol": Pata,
  bluey: Perro,
  cars: Carro,
  stitch: Alien,
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

export function iconoDe(nombre: string): ComponentType<Props> {
  return MAPA[nombre.trim().toLowerCase()] ?? Generico;
}
