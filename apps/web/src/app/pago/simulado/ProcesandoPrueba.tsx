"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import styles from "../Pago.module.css";

const ESPERA_MS = 1200;

export default function ProcesandoPrueba({ destino }: { destino: string }) {
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => router.replace(destino), ESPERA_MS);
    return () => clearTimeout(t);
  }, [destino, router]);

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta} role="status" aria-live="polite">
        <h1 className={styles.titulo}>Procesando pago de prueba…</h1>
        <p className={styles.texto}>Esto toma solo un momento. No cierres esta ventana.</p>
      </div>
    </div>
  );
}
