"use client";

// P4 — "Editar" una lista ya publicada. Clona la vigente en una versión nueva
// SIN revisar (`nuevaVersion`) y cae en el revisor de cuatro paneles con esa
// versión, para corregirla sin tocar la que ven los acudientes. Reemplaza el
// enlace interino a /onboarding.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FalloListas, nuevaVersion } from "@/lib/api-listas";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  colegioId: string;
  grado: string;
  anioLectivo: number;
}

export default function EditarLista({ colegioId, grado, anioLectivo }: Props) {
  const router = useRouter();
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function editar() {
    setCreando(true);
    setError(null);
    try {
      const { version_id } = await nuevaVersion(colegioId, grado, anioLectivo);
      router.push(`/onboarding/${encodeURIComponent(version_id)}`);
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo crear la versión.");
      setCreando(false);
    }
  }

  return (
    <div className={styles.accionesGrado}>
      <button type="button" className={styles.botonPrincipal} onClick={editar} disabled={creando}>
        {creando ? "Creando versión…" : "Editar (nueva versión)"}
      </button>
      {error ? <p className={styles.pistaError}>{error}</p> : null}
    </div>
  );
}
