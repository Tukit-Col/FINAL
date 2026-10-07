"use client";

// P4 — "Editar kits" de un grado ya publicado. Los kits vigentes no se tocan:
// se abre (o se retoma) un borrador con su copia, que es la versión siguiente,
// y se cae en la consola de revisión para corregir los renglones de cada kit
// —los no reconocidos van marcados—. Publicarlo allí lo vuelve el canónico.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { abrirBorradorKits, FalloApi } from "@/lib/api-navegador";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  /** El canónico vigente del grado. */
  canonicoId: string;
  /** El borrador ya abierto, si lo hay: se retoma en vez de crear otro. */
  borradorId: string | null;
}

export default function EditarKits({ canonicoId, borradorId }: Props) {
  const router = useRouter();
  const [abriendo, setAbriendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function editar() {
    setAbriendo(true);
    setError(null);
    try {
      const { trabajo_id } = borradorId
        ? { trabajo_id: borradorId }
        : await abrirBorradorKits(canonicoId);
      router.push(`/trabajos/${encodeURIComponent(trabajo_id)}`);
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No se pudo abrir la edición.");
      setAbriendo(false);
    }
  }

  return (
    <div className={styles.accionesGrado}>
      <button type="button" className={styles.botonPrincipal} onClick={editar} disabled={abriendo}>
        {abriendo ? "Abriendo…" : borradorId ? "Continuar edición" : "Editar kits"}
      </button>
      {error ? <p className={styles.pistaError}>{error}</p> : null}
    </div>
  );
}
