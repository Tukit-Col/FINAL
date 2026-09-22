import styles from "./Sidebar.module.css";

const navItems = [
  {
    id: "perfil",
    label: "Perfil",
    href: "/perfil",
    active: false,
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="10" cy="7" r="3.5" />
        <path d="M3 17c0-3.314 3.134-6 7-6s7 2.686 7 6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "pedidos",
    label: "Mis Pedidos",
    href: "/pedidos",
    active: false,
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M3 4h14M3 8h14M3 12h10M3 16h6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "hijos",
    label: "Perfiles de Hijos",
    href: "/hijos",
    active: true,
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M9 11a4 4 0 100-8 4 4 0 000 8z" />
        <path d="M15 13a3 3 0 110 6M3 19c0-2.761 2.686-5 6-5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "kits",
    label: "Kits Guardados",
    href: "/kits",
    active: false,
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 18l-6.828-7.172a4 4 0 010-5.656z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "buscador",
    label: "Buscador de Colegios",
    href: "/buscador",
    active: false,
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M10 2L2 6v4c0 4.418 3.36 8.545 8 9.5C18.64 18.545 18 14.418 18 10V6l-8-4z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

const secondaryItems = [
  {
    id: "direcciones",
    label: "Direcciones",
    href: "/direcciones",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M10 2a6 6 0 00-6 6c0 4.5 6 10 6 10s6-5.5 6-10a6 6 0 00-6-6z" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="10" cy="8" r="2" />
      </svg>
    ),
  },
  {
    id: "pagos",
    label: "Métodos de Pago",
    href: "/pagos",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="2" y="5" width="16" height="11" rx="2" />
        <path d="M2 9h16" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      {/* Account */}
      <div className={styles.sidebar__account}>
        <div className={styles["sidebar__account-label"]}>Mi Cuenta</div>
        <div className={styles["sidebar__account-name"]}>Camila R.</div>
      </div>

      {/* Main nav */}
      <nav className={styles.sidebar__nav}>
        {navItems.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className={[
              styles.sidebar__item,
              item.active ? styles["sidebar__item--active"] : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className={styles.sidebar__icon}>{item.icon}</span>
            {item.label}
          </a>
        ))}

        <div className={styles.sidebar__separator} />

        {secondaryItems.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className={styles.sidebar__item}
          >
            <span className={styles.sidebar__icon}>{item.icon}</span>
            {item.label}
          </a>
        ))}

        {/* Cerrar sesión */}
        <a
          href="/logout"
          className={[styles.sidebar__item, styles["sidebar__item--danger"]].join(" ")}
        >
          <span className={styles.sidebar__icon}>
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M7 17H4a1 1 0 01-1-1V4a1 1 0 011-1h3" strokeLinecap="round" />
              <path d="M14 13l4-3-4-3M18 10H8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          Cerrar Sesión
        </a>
      </nav>
    </aside>
  );
}
