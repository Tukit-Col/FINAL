"use client";

// Lo que ve quien llego al tope del limite de tasa (ADR 0047) al abrir una
// pagina: el mensaje del gateway, que ya dice cuanto esperar, y un boton para
// volver a pedirla. No lo manda a `/ingresar` ni le pinta secciones vacias: su
// sesion y sus datos siguen ahi. De cliente solo por el boton (`refresh` vuelve
// a renderizar la pagina en el servidor sin recargar todo).

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
