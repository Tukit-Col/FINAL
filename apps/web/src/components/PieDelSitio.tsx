import Link from "next/link";
import styles from "@/app/legal/Legal.module.css";

const ENLACES = [
  { href: "/legal/privacidad", texto: "Política de datos personales" },
  { href: "/legal/terminos", texto: "Términos y condiciones" },
  { href: "/legal/retracto", texto: "Retracto y garantía" },
  { href: "/ayuda", texto: "Ayuda" },
];

export default function PieDelSitio() {
  return (
    <footer className={styles.pie}>
      <div className={styles.pieInterior}>
        <span>© Tukit. La lista del colegio, resuelta.</span>
        <nav aria-label="Información legal">
          <ul className={styles.pieEnlaces}>
            {ENLACES.map((e) => (
              <li key={e.href}>
                <Link href={e.href}>{e.texto}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
