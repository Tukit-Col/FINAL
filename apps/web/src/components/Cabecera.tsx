import Link from "next/link";
import { Home, LifeBuoy, Sparkles, LogIn, LayoutDashboard } from "lucide-react";
import { destinoDe, urlAdmin } from "@tukit/contrato/servidor";
import { sesionActual } from "@/lib/sesion";
import SalirBoton from "./SalirBoton";
import styles from "./Cabecera.module.css";

const ENLACES = [
  { href: "/", texto: "Inicio", Icono: Home },
  { href: "/ayuda", texto: "Ayuda", Icono: LifeBuoy },
];

export default async function Cabecera() {
  // La sesion se lee en el servidor: el boton de ingreso cambia a "mi cuenta"
  // (al destino que le toca por rol) mas "cerrar sesion", sin que el rol lo
  // decida ningun componente de cliente.
  const sesion = await sesionActual();
  const destino = sesion ? destinoDe(sesion) : null;
  const urlCuenta =
    destino?.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino?.ruta ?? "/dashboard";

  return (
    <header className={styles.cabecera}>
      <div className={styles.interior}>
        <Link href="/" className={styles.logo}>
          <span className={styles.marca} aria-hidden="true">
            {/* Librito + estrella del logo: la tiendita que arma la lista. */}
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M4 5.5C4 4.7 4.7 4 5.5 4H11v14H5.5C4.7 18 4 17.3 4 16.5V5.5Z"
                fill="#fff"
                fillOpacity="0.92"
              />
              <path
                d="M20 5.5C20 4.7 19.3 4 18.5 4H13v14h5.5c.8 0 1.5-.7 1.5-1.5V5.5Z"
                fill="#fff"
                fillOpacity="0.72"
              />
              <path
                d="M12 6.2l1.1 2.3 2.5.3-1.8 1.7.5 2.5L12 11.9l-2.3 1.1.5-2.5-1.8-1.7 2.5-.3L12 6.2Z"
                fill="var(--clay-estrella)"
              />
            </svg>
          </span>
          <span className={styles.nombre}>Tukit</span>
        </Link>

        <nav className={styles.nav} aria-label="Principal">
          {ENLACES.map(({ href, texto, Icono }) => (
            <Link key={href} href={href} className={styles.enlace}>
              <Icono size={16} aria-hidden="true" strokeWidth={2.4} />
              <span>{texto}</span>
            </Link>
          ))}
        </nav>

        <div className={styles.acciones}>
          {sesion ? (
            <>
              <Link href={urlCuenta} className={styles.cuenta}>
                <LayoutDashboard size={16} aria-hidden="true" strokeWidth={2.4} />
                <span>Mi cuenta</span>
              </Link>
              <SalirBoton className={styles.salir} />
            </>
          ) : (
            <Link href="/ingresar" className={styles.ingresar}>
              <LogIn size={16} aria-hidden="true" strokeWidth={2.4} />
              <span>Ingresar</span>
            </Link>
          )}
          <Link href="/empezar" className={styles.accion}>
            <Sparkles size={16} aria-hidden="true" strokeWidth={2.6} />
            Armar mi kit
          </Link>
        </div>
      </div>
    </header>
  );
}
