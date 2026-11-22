"use client";

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
  volverA?: string;
  enFila?: boolean;
}

export default function BorrarTrabajo({ trabajoId, estado, volverA, enFila = false }: Props) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
