"use client";

// Región 4 del revisor: "Previsualizar los 3 kits" (P4, cierre de la brecha).
//
// El administrador, parado sobre una versión curada, pide ver los tres kits que
// saldrían de ella ANTES de publicar. Esto arma un trabajo de preview (no el del
// acudiente) con `previewDeVersion` y navega a la página de vista previa, que lo
// lee con `trabajoAdmin`. Previsualizar NO aprueba: el botón "Aprobar y publicar"
// (`cerrarLista`) sigue siendo el único que publica, y vive aparte.

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
      router.push(
        `/onboarding/${encodeURIComponent(versionId)}/preview/${encodeURIComponent(trabajo_id)}`,
      );
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
        {armando ? "Armando la vista previa…" : "Previsualizar los 3 kits"}
      </button>
      <span className={styles.faltante}>
        Ve los tres kits que saldrían de esta versión sin publicarla. Es una vista de solo
        lectura: publicar es el otro botón.
      </span>
      {error ? <p className={styles.errorCaja}>{error}</p> : null}
    </div>
  );
}
