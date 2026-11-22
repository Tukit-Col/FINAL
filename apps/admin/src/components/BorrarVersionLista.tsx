"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { eliminarVersionLista, FalloListas } from "@/lib/api-listas";
import styles from "./BorrarVersionLista.module.css";

interface Props {
  versionId: string;
  grado: string;
  acudienteEsperando: boolean;
}

export default function BorrarVersionLista({ versionId, grado, acudienteEsperando }: Props) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function borrar(): Promise<void> {
    setError(null);
    setEnviando(true);
    try {
      await eliminarVersionLista(versionId);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No pudimos eliminar la lista.");
      if (causa instanceof FalloListas && (causa.estado === 409 || causa.estado === 404)) {
        router.refresh();
      }
      setEnviando(false);
    }
  }

  if (!confirmando) {
    return (
      <button type="button" className={styles.disparador} onClick={() => setConfirmando(true)}>
        Eliminar
      </button>
    );
  }

  return (
    <span>
      <span
        className={styles.confirmacion}
        role="alertdialog"
        aria-label={`Eliminar la lista de ${grado}`}
        title={`Se borran los renglones y el PDF de la lista de ${grado}.`}
      >
        <span className={styles.pregunta}>¿Eliminar?</span>
        {acudienteEsperando ? <span className={styles.aviso}>Un acudiente la espera</span> : null}
        <button
          type="button"
          className={styles.confirmar}
          disabled={enviando}
          onClick={() => void borrar()}
        >
          {enviando ? "Eliminando…" : "Sí, eliminar"}
        </button>
        <button
          type="button"
          className={styles.cancelar}
          disabled={enviando}
          onClick={() => setConfirmando(false)}
        >
          Cancelar
        </button>
      </span>
      {error ? <span className={styles.error}>{error}</span> : null}
    </span>
  );
}
