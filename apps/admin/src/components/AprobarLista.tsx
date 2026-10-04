"use client";

// Región 4 del revisor (P4): aprobar y publicar. El onboarding crea una VERSIÓN
// de lista, no un `TrabajoAdmin`, así que no hay tres kits que armar aquí
// (`ConsolaRevision` toma un `TrabajoAdmin` y no existe una forma en el contrato
// de derivarlo de una versión — ver `notas` de la página). Lo que sí existe es
// `cerrarLista(version_id)`: cierra la versión, la marca revisada y deja el par
// (colegio, grado) disponible para los acudientes. Tras cerrar, `router.refresh`
// re-lee la revisión (que ya vendrá `revisada`) y luego se navega al perfil.
//
// Antes de aprobar, la guarda (`lib/aprobar`) dice qué pasará con la vista
// previa: si la lista cambió desde que se previsualizó el botón se desactiva
// (aprobar tiraría los ajustes), con dudosas se pide confirmar (el kit queda
// en la Cola) y sin vista previa solo se informa.

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { VistaPreviaLista } from "@tukit/contrato";
import { cerrarLista, FalloListas } from "@/lib/api-listas";
import { guardaDeAprobacion } from "@/lib/aprobar";
import styles from "@/app/onboarding/Onboarding.module.css";

interface Props {
  versionId: string;
  colegioId: string;
  grado: string;
  revisada: boolean;
  // undefined = no se pudo leer (ver `lib/revisor`).
  vistaPrevia: VistaPreviaLista | null | undefined;
  // Hay un acudiente a quien publicarle el kit al aprobar.
  tieneContacto: boolean;
}

export default function AprobarLista({
  versionId,
  colegioId,
  grado,
  revisada,
  vistaPrevia,
  tieneContacto,
}: Props) {
  const router = useRouter();
  const [cerrando, setCerrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const guarda = guardaDeAprobacion(vistaPrevia, tieneContacto);

  async function aprobar() {
    if (guarda.tipo === "bloqueada") return;
    if (guarda.tipo === "confirmar" && !window.confirm(guarda.mensaje)) return;
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
      <button
        type="button"
        className={styles.principal}
        onClick={aprobar}
        disabled={cerrando || guarda.tipo === "bloqueada"}
      >
        {cerrando ? "Publicando…" : "Aprobar y publicar"}
      </button>
      <span className={styles.faltante}>
        Publicar deja el par ({colegioId}, {grado}) disponible para los acudientes.
      </span>
      {guarda.tipo === "bloqueada" ? (
        <p className={styles.errorCaja} role="status">
          {guarda.mensaje}
        </p>
      ) : guarda.tipo === "confirmar" ? (
        <p className={styles.faltante} role="status">
          {guarda.mensaje}{" "}
          <Link href={`/trabajos/${encodeURIComponent(guarda.trabajoId)}`}>
            Abrir la vista previa →
          </Link>
        </p>
      ) : guarda.tipo === "aviso" ? (
        <p className={styles.faltante} role="status">
          {guarda.mensaje}
        </p>
      ) : null}
      {error ? <p className={styles.errorCaja}>{error}</p> : null}
    </div>
  );
}
