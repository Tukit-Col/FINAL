"use client";

// Región 4 del revisor (P4): aprobar y publicar. El onboarding crea una VERSIÓN
// de lista, no un `TrabajoAdmin`, así que no hay tres kits que armar aquí
// (`ConsolaRevision` toma un `TrabajoAdmin` y no existe una forma en el contrato
// de derivarlo de una versión — ver `notas` de la página). Lo que sí existe es
// `cerrarLista(version_id)`: cierra la versión, la marca revisada y deja el par
// (colegio, grado) disponible para los acudientes. Tras cerrar, `router.refresh`
// re-lee la revisión (que ya vendrá `revisada`) y luego se navega al perfil.

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
