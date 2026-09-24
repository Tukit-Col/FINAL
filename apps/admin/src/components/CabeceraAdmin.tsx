"use client";

// Barra del back-office. Antes era un solo enlace de vuelta a la cola; ahora es
// la navegación de un back-office de e-commerce con cinco secciones. Es de
// cliente por una sola razón: `usePathname` marca en qué sección estás. La
// lógica de cada pantalla sigue en su propio Server Component.

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  PackageSearch,
  School,
  Truck,
} from "lucide-react";
import SalirBoton from "./SalirBoton";
import styles from "./CabeceraAdmin.module.css";

// El orden es el del flujo de trabajo: primero el pulso del negocio (Panel),
// luego lo que hay que verificar (Cola) —donde ahora también se sube una lista
// nueva, sin pantalla aparte, y donde una lista de acudiente trae su colegio y
// grado para crearlos al aprobar—, la BD durable de colegios y listas
// (Colegios), lo que hay en catálogo (Catálogo), lo que hay que mover
// (Logística) y lo que hay que responder (Tickets).
const SECCIONES = [
  { href: "/", etiqueta: "Panel", Icono: LayoutDashboard },
  { href: "/cola", etiqueta: "Cola", Icono: ClipboardList },
  { href: "/colegios", etiqueta: "Colegios", Icono: School },
  { href: "/catalogo", etiqueta: "Catálogo", Icono: PackageSearch },
  { href: "/logistica", etiqueta: "Logística", Icono: Truck },
  { href: "/tickets", etiqueta: "Tickets", Icono: LifeBuoy },
] as const;

// Un enlace está activo si la ruta actual empieza por su href. El Panel es la
// casa ("/") y solo se enciende en la raíz exacta. La Cola vive en "/cola" y
// además es dueña de "/trabajos/…" (un ingreso de acudiente) y de
// "/onboarding/…" (el revisor de una versión): ambas rutas son revisar algo de
// la cola, así que encienden el mismo ítem.
function estaActiva(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/cola")
    return (
      pathname === "/cola" ||
      pathname.startsWith("/trabajos") ||
      pathname.startsWith("/onboarding")
    );
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function CabeceraAdmin() {
  const pathname = usePathname() ?? "/";

  return (
    <header className={styles.cabecera}>
      <Link href="/" className={styles.logo}>
        <span className={styles.marca} aria-hidden="true">
          <svg viewBox="0 0 18 18" fill="none">
            <path d="M9 1L16.5 5.25V12.75L9 17L1.5 12.75V5.25L9 1Z" fill="white" fillOpacity="0.9" />
            <path d="M9 5L13 7.5V12L9 14L5 12V7.5L9 5Z" fill="white" />
          </svg>
        </span>
        <span className={styles.nombre}>Tukit</span>
        <span className={styles.consola}>Back-office</span>
      </Link>

      <div className={styles.derecha}>
        <nav className={styles.nav} aria-label="Secciones del back-office">
          {SECCIONES.map(({ href, etiqueta, Icono }) => {
            const activa = estaActiva(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={`${styles.item} ${activa ? styles.itemActivo : ""}`}
                aria-current={activa ? "page" : undefined}
              >
                <Icono size={16} strokeWidth={2.2} aria-hidden="true" />
                {etiqueta}
              </Link>
            );
          })}
        </nav>
        <SalirBoton />
      </div>
    </header>
  );
}
