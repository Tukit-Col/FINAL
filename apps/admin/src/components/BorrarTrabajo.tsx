"use client";

// Borra un trabajo desechable (preview repetido, encolado, en espera, fallido).
//
// Dos pasos a proposito, como `DecisionTrabajo`: borrar es irreversible y
// cascadea kits y etapas. Un `publicado` es el kit canonico y esta protegido:
// ni se ofrece el boton, y si aun asi se intenta el backend responde 409.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import type { EstadoTrabajo } from "@tukit/contrato";
import { eliminarTrabajo, FalloApi } from "@/lib/api-navegador";
import barra from "./BorrarTrabajo.module.css";
import fila from "./BorrarVersionLista.module.css";

interface Props {
  trabajoId: string;
  estado: EstadoTrabajo;
  /** A donde ir tras borrar. Sin valor, refresca la vista actual (la cola). */
  volverA?: string;
  /** En una fila de la cola: boton en pastilla y confirmacion en la misma linea. */
  enFila?: boolean;
}

export default function BorrarTrabajo({ trabajoId, estado, volverA, enFila = false }: Props) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Un publicado no se borra: es el kit canonico. No se muestra el boton.
  if (estado === "publicado") return null;

  async function borrar(): Promise<void> {
    setError(null);
    setEnviando(true);
    try {
      await eliminarTrabajo(trabajoId);
      if (volverA) router.push(volverA);
      else router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos borrar el trabajo.");
      // Si otro ya lo publico (409) o ya no existe (404), refrescar deja la
      // vista al dia y el boton desaparece solo.
      if (causa instanceof FalloApi && (causa.estado === 409 || causa.estado === 404)) {
        router.refresh();
      }
      setEnviando(false);
    }
  }

  if (enFila) {
    if (!confirmando) {
      return (
        <button type="button" className={fila.disparador} onClick={() => setConfirmando(true)}>
          Eliminar
        </button>
      );
    }
    return (
      <span>
        <span className={fila.confirmacion} role="alertdialog" aria-label="Eliminar el trabajo">
          <span className={fila.pregunta}>¿Eliminar?</span>
          <button
            type="button"
            className={fila.confirmar}
            disabled={enviando}
            onClick={() => void borrar()}
          >
            {enviando ? "Eliminando…" : "Sí, eliminar"}
          </button>
          <button
            type="button"
            className={fila.cancelar}
            disabled={enviando}
            onClick={() => setConfirmando(false)}
          >
            Cancelar
          </button>
        </span>
        {error ? <span className={fila.error}>{error}</span> : null}
      </span>
    );
  }

  // En la barra del detalle: un boton discreto que, al pulsarlo, se vuelve una
  // confirmacion en la misma linea. Borrar es irreversible; no merece un rojo
  // gritando antes de que alguien lo pida.
  return (
    <div className={barra.contenedor}>
      {confirmando ? (
        <div className={barra.confirmacion} role="alertdialog" aria-label="Eliminar el trabajo">
          <span className={barra.pregunta}>¿Eliminar este trabajo? No se puede deshacer.</span>
          <button
            type="button"
            className={barra.confirmar}
            disabled={enviando}
            onClick={() => void borrar()}
          >
            {enviando ? "Eliminando…" : "Sí, eliminar"}
          </button>
          <button
            type="button"
            className={barra.cancelar}
            disabled={enviando}
            onClick={() => setConfirmando(false)}
          >
            Cancelar
          </button>
        </div>
      ) : (
        <button type="button" className={barra.disparador} onClick={() => setConfirmando(true)}>
          <Trash2 size={15} aria-hidden="true" />
          Eliminar trabajo
        </button>
      )}
      {error ? <p className={barra.error}>{error}</p> : null}
    </div>
  );
}
