"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { abrirBorradorKits, FalloApi } from "@/lib/api-navegador";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  canonicoId: string;
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
