import Image from "next/image";
import Link from "next/link";
import { Home, LifeBuoy, Sparkles, LogIn, LayoutDashboard } from "lucide-react";
import { destinoDe, urlAdmin } from "@tukit/contrato/servidor";
import { esLimiteDeTasa } from "@/lib/limite";
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
  // Con el cupo agotado (429) no se sabe el rol, pero la cookie sigue viva: se
  // pinta "Mi cuenta" (al panel) y no "Ingresar", que invitaria a entrar otra
  // vez. El aviso con la espera lo da la pagina.
  let sesion: Awaited<ReturnType<typeof sesionActual>>;
  let conSesion: boolean;
  try {
    sesion = await sesionActual();
    conSesion = sesion !== null;
  } catch (causa) {
    if (!esLimiteDeTasa(causa)) throw causa;
    sesion = null;
    conSesion = true;
  }
  const destino = sesion ? destinoDe(sesion) : null;
  const urlCuenta =
    destino?.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino?.ruta ?? "/dashboard";

  return (
    <header className={styles.cabecera}>
      <div className={styles.interior}>
        <Link href="/" className={styles.logo}>
          <Image
            src="/marca/tukit-marca.webp"
            alt=""
            width={80}
            height={90}
            priority
            className={styles.marca}
          />
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
          {conSesion ? (
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
