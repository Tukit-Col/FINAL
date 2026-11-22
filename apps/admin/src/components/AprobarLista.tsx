"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cerrarLista, FalloListas } from "@/lib/api-listas";
import styles from "@/app/onboarding/Onboarding.module.css";

interface Props {
  versionId: string;
  colegioId: string;
  grado: string;
  revisada: boolean;
}

export default function AprobarLista({ versionId, colegioId, grado, revisada }: Props) {
  const router = useRouter();
  const [cerrando, setCerrando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function aprobar() {
    setCerrando(true);
    setError(null);
    try {
      await cerrarLista(versionId);
      router.push(`/colegios/${encodeURIComponent(colegioId)}/${encodeURIComponent(grado)}`);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo publicar la lista.");
      setCerrando(false);
    }
  }

  if (revisada) {
    return (
      <p className={styles.faltante}>
        Esta versión ya está publicada. Los acudientes de {grado} ya la ven.
      </p>
    );
  }

  return (
    <div className={styles.barraAccion}>
      <button type="button" className={styles.principal} onClick={aprobar} disabled={cerrando}>
        {cerrando ? "Publicando…" : "Aprobar y publicar"}
      </button>
      <span className={styles.faltante}>
        Publicar deja el par ({colegioId}, {grado}) disponible para los acudientes.
      </span>
      {error ? <p className={styles.errorCaja}>{error}</p> : null}
    </div>
  );
}
