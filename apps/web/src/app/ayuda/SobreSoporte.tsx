import styles from "./Ayuda.module.css";

export default function SobreSoporte() {
  return (
    <svg viewBox="0 0 200 200" className={styles.claySvg} aria-hidden="true">
      <defs>
        <linearGradient id="sop-sobre" x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" stopColor="#6fc0f0" />
          <stop offset="1" stopColor="#1e40af" />
        </linearGradient>
        <linearGradient id="sop-solapa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#8fd3f4" />
          <stop offset="1" stopColor="#2f8fd6" />
        </linearGradient>
        <linearGradient id="sop-burbuja" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#eef3fb" />
        </linearGradient>
        <linearGradient id="sop-estrella" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd75e" />
          <stop offset="1" stopColor="#e0a92b" />
        </linearGradient>
      </defs>

      <rect x="34" y="66" width="132" height="94" rx="20" fill="url(#sop-sobre)" />
      <rect x="34" y="66" width="132" height="30" rx="20" fill="#ffffff" opacity="0.16" />
      <path
        d="M40 74 Q100 128 160 74 L160 84 Q100 138 40 84 Z"
        fill="url(#sop-solapa)"
      />
      <path d="M40 74 Q100 128 160 74" fill="none" stroke="#ffffff" strokeOpacity="0.4" strokeWidth="3" />

      <g transform="translate(96 20)">
        <rect x="0" y="0" width="86" height="60" rx="18" fill="url(#sop-burbuja)" />
        <path d="M22 58 L22 74 L40 58 Z" fill="#eef3fb" />
        <rect x="16" y="18" width="54" height="7" rx="3.5" fill="#c9d3e0" />
        <rect x="16" y="34" width="38" height="7" rx="3.5" fill="#c9d3e0" />
      </g>

      <g transform="translate(100 118)">
        <path
          d="M0 -24 L7 -8 L24 -7 L11 4 L15 22 L0 12 L-15 22 L-11 4 L-24 -7 L-7 -8 Z"
          fill="url(#sop-estrella)"
        />
        <path d="M0 -24 L7 -8 L24 -7 L11 4 Z" fill="#ffffff" opacity="0.26" />
      </g>
    </svg>
  );
}
