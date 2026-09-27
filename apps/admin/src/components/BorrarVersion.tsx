"use client";

// Descarta de la cola una versión de lista SIN revisar (una sugerencia que no
// va, un onboarding equivocado).
//
// Dos pasos a propósito, como `BorrarTrabajo`: borrar cascadea sus renglones y
// propuestas. Una versión ya revisada es la lista oficial del colegio y está
// protegida en el backend (409 `lista_ya_revisada`); a la cola solo llegan
// versiones sin revisar, así que aquí siempre se ofrece el botón.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { eliminarVersion, FalloListas } from "@/lib/api-listas";
import styles from "./Revision.module.css";

export default function BorrarVersion({ versionId }: { versionId: string }) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function borrar(): Promise<void> {
    setError(null);
    setEnviando(true);
    try {
      await eliminarVersion(versionId);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No pudimos borrar la versión.");
      // Si otro ya la aprobó (409) o ya no existe (404), refrescar deja la vista
      // al día y la fila se ajusta sola.
      if (causa instanceof FalloListas && (causa.estado === 409 || causa.estado === 404)) {
        router.refresh();
      }
      setEnviando(false);
    }
  }

  return (
    <div className={styles.borrar}>
      {confirmando ? (
        <div className={styles.botonera}>
          <button
            type="button"
            className={styles.peligro}
            disabled={enviando}
            onClick={() => void borrar()}
          >
            Sí, descartar
          </button>
          <button type="button" className={styles.plano} onClick={() => setConfirmando(false)}>
            Cancelar
          </button>
        </div>
      ) : (
        <button type="button" className={styles.plano} onClick={() => setConfirmando(true)}>
          Descartar
        </button>
      )}
      {error ? <p className={styles.error}>{error}</p> : null}
    </div>
  );
}
