"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  Mail,
  PackageSearch,
  School,
  Truck,
  Users,
} from "lucide-react";
import SalirBoton from "./SalirBoton";
import styles from "./CabeceraAdmin.module.css";

const SECCIONES = [
  { href: "/", etiqueta: "Panel", Icono: LayoutDashboard },
  { href: "/cola", etiqueta: "Cola", Icono: ClipboardList },
  { href: "/colegios", etiqueta: "Colegios", Icono: School },
  { href: "/clientes", etiqueta: "Clientes", Icono: Users },
  { href: "/catalogo", etiqueta: "Catálogo", Icono: PackageSearch },
  { href: "/logistica", etiqueta: "Logística", Icono: Truck },
  { href: "/tickets", etiqueta: "Tickets", Icono: LifeBuoy },
  { href: "/correos", etiqueta: "Correos", Icono: Mail },
] as const;

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
        <Image src="/marca/logo.png" alt="" width={34} height={30} priority className={styles.marca} />
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
