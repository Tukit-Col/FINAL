import Link from "next/link";
import type { ReactNode } from "react";
import { FECHA_VIGENCIA, VERSION_TEXTOS_LEGALES, esPendiente } from "./datos-legales";
import styles from "./Legal.module.css";

const DOCUMENTOS = [
  { href: "/legal/privacidad", texto: "Datos personales" },
  { href: "/legal/terminos", texto: "Términos y condiciones" },
  { href: "/legal/retracto", texto: "Retracto y garantía" },
];

/** Un dato del responsable: si todavía es un pendiente, se marca como tal. */
export function Dato({ valor }: { valor: string }) {
  return esPendiente(valor) ? (
    <mark className={styles.pendiente} title="El equipo de Tukit debe completar este dato">
      {valor}
    </mark>
  ) : (
    <>{valor}</>
  );
}

export default function DocumentoLegal({
  titulo,
  resumen,
  children,
}: {
  titulo: string;
  resumen: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.pagina}>
      <nav className={styles.otros} aria-label="Documentos legales">
        {DOCUMENTOS.map((d) => (
          <Link key={d.href} href={d.href} className={styles.enlaceDoc}>
            {d.texto}
          </Link>
        ))}
      </nav>
      <article className={styles.documento}>
        <header>
          <h1>{titulo}</h1>
          <p className={styles.resumen}>{resumen}</p>
          <p className={styles.vigencia}>
            Vigente desde el {FECHA_VIGENCIA} · versión {VERSION_TEXTOS_LEGALES}
          </p>
        </header>
        {children}
      </article>
    </div>
  );
}
