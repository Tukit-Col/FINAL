"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import styles from "./AvisoLimite.module.css";

export default function AvisoLimite({
  mensaje,
  conSesion,
}: {
  mensaje: string;
  conSesion: boolean;
}) {
  const router = useRouter();
  const [consultando, empezar] = useTransition();

  return (
    <div className={styles.pagina}>
      <section className={styles.tarjeta} role="alert">
        <h1 className={styles.titulo}>Danos un momento</h1>
        <p className={styles.texto}>{mensaje}</p>
        {conSesion ? (
          <p className={styles.texto}>Tu sesión sigue abierta: no tienes que volver a entrar.</p>
        ) : null}
        <button
          type="button"
          className={styles.boton}
          disabled={consultando}
          onClick={() => empezar(() => router.refresh())}
        >
          {consultando ? "Consultando…" : "Intentar de nuevo"}
        </button>
      </section>
    </div>
  );
}
