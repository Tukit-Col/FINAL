"use client";

import { useEffect, useState, type MouseEvent } from "react";
import { Users, Package, ClipboardList, LifeBuoy } from "lucide-react";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import styles from "./Sidebar.module.css";

const SECCIONES = [
  { id: "hijos", label: "Perfiles de hijos", icon: Users },
  { id: "solicitudes", label: "Mis solicitudes", icon: ClipboardList },
  { id: "pedidos", label: "Mis pedidos", icon: Package },
  { id: "casos", label: "Mis casos", icon: LifeBuoy },
];

export default function NavSecciones() {
  const [activa, setActiva] = useState<string | null>(null);

  useEffect(() => {
    const elementos = SECCIONES.map((s) => document.getElementById(s.id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (elementos.length === 0) return;
    const observador = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting) setActiva(entrada.target.id);
        }
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    elementos.forEach((el) => observador.observe(el));
    return () => observador.disconnect();
  }, []);

  function irA(evento: MouseEvent<HTMLAnchorElement>, id: string) {
    const destino = document.getElementById(id);
    if (!destino) return;
    evento.preventDefault();
    destino.scrollIntoView({
      behavior: prefiereMenosMovimiento() ? "auto" : "smooth",
      block: "start",
    });
    history.replaceState(null, "", `#${id}`);
    setActiva(id);
  }

  return (
    <>
      {SECCIONES.map(({ id, label, icon: Icon }) => (
        <a
          key={id}
          href={`#${id}`}
          onClick={(evento) => irA(evento, id)}
          aria-current={activa === id ? "location" : undefined}
          className={`${styles.sidebar__item} ${activa === id ? styles["sidebar__item--activo"] : ""}`}
        >
          <span className={styles.sidebar__icon}>
            <Icon size={17} strokeWidth={2} aria-hidden="true" />
          </span>
          {label}
        </a>
      ))}
    </>
  );
}
