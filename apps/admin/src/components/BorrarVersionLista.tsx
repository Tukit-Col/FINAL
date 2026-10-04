"use client";

// Saca de la cola una versión de lista sin revisar (subida repetida, grado
// equivocado, una que se va a volver a subir).
//
// Dos pasos a propósito, como `BorrarTrabajo`: borrar es irreversible y se
// lleva los renglones y el PDF. Si un acudiente subió la lista, su pedido no se
// arma nunca: la confirmación lo dice antes, no después.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { eliminarVersionLista, FalloListas } from "@/lib/api-listas";
import styles from "./BorrarVersionLista.module.css";

interface Props {
  versionId: string;
  /** Grado, para que la pregunta diga qué se va a borrar. */
  grado: string;
  /** Si un acudiente está esperando el kit de esta lista. */
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
      // Si otro ya la aprobó (409) o ya no existe (404), refrescar deja la
      // cola al día y la fila desaparece sola.
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
    <div className={styles.confirmacion} role="alertdialog" aria-label={`Eliminar la lista de ${grado}`}>
      <p className={styles.pregunta}>¿Eliminar la lista de {grado}? Se borran sus renglones y el PDF.</p>
      {acudienteEsperando ? (
        <p className={styles.aviso}>Un acudiente la está esperando: su kit no se va a armar.</p>
      ) : null}
      <div className={styles.botones}>
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
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
    </div>
  );
}
