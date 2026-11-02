import Link from "next/link";
import styles from "./Legal.module.css";

export const metadata = { title: "Información legal | Tukit" };

const DOCUMENTOS = [
  {
    href: "/legal/privacidad",
    titulo: "Tratamiento de datos personales",
    texto: "Qué datos tuyos y de tus hijos guardamos, para qué y cómo ejercer tus derechos.",
  },
  {
    href: "/legal/terminos",
    titulo: "Términos y condiciones",
    texto: "Cómo funciona Tukit, qué compras y cómo se paga.",
  },
  {
    href: "/legal/retracto",
    titulo: "Derecho de retracto y garantía",
    texto: "Cómo devolver un pedido en los 5 días hábiles siguientes a recibirlo y qué cubre la garantía.",
  },
];

export default function PaginaLegal() {
  return (
    <div className={styles.pagina}>
      <article className={styles.documento}>
        <h1>Información legal</h1>
        <p className={styles.resumen}>
          Aquí está lo que debes saber antes de usar Tukit y de pagar un pedido, en lenguaje claro.
        </p>
        <div className={styles.indice}>
          {DOCUMENTOS.map((d) => (
            <Link key={d.href} href={d.href} className={styles.tarjetaDoc}>
              <strong>{d.titulo}</strong>
              <span>{d.texto}</span>
            </Link>
          ))}
        </div>
      </article>
    </div>
  );
}
