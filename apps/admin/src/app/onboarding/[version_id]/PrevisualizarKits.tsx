"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye } from "lucide-react";
import { FalloListas, previsualizarVersion } from "@/lib/api-listas";
import styles from "@/app/onboarding/Onboarding.module.css";

interface Props {
  versionId: string;
  colegioId: string;
  grado: string;
  anioLectivo: number;
}

export default function PrevisualizarKits({ versionId, colegioId, grado, anioLectivo }: Props) {
  const router = useRouter();
  const [armando, setArmando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function previsualizar() {
    setArmando(true);
    setError(null);
    try {
      const { trabajo_id } = await previsualizarVersion(versionId, {
        colegio_id: colegioId,
        grado,
        anio_lectivo: anioLectivo,
      });
      router.push(`/trabajos/${encodeURIComponent(trabajo_id)}`);
    } catch (causa) {
      setError(
        causa instanceof FalloListas ? causa.message : "No pudimos armar la vista previa.",
      );
      setArmando(false);
    }
  }

  return (
    <div className={styles.barraAccion}>
      <button
        type="button"
        className={styles.secundario}
        onClick={previsualizar}
        disabled={armando}
      >
        <Eye size={15} strokeWidth={2.4} aria-hidden="true" />
        {armando ? "Armando la vista previa…" : "Previsualizar los kits"}
      </button>
      <span className={styles.faltante}>
        Opcional. Abre en la consola de revisión el Ahorrador y el Premium que saldrían de
        esta versión, sin publicarla: ahí puedes validar y cambiar productos antes de guardarlos.
      </span>
      {error ? <p className={styles.errorCaja}>{error}</p> : null}
    </div>
  );
}
