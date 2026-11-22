"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { type ItemRevision } from "@tukit/contrato";
import { agregarItemLista, quitarItemLista, FalloListas } from "@/lib/api-listas";
import styles from "@/app/onboarding/Onboarding.module.css";

export default function DividirRenglon({
  versionId,
  item,
  onListo,
}: {
  versionId: string;
  item: ItemRevision;
  onListo: () => void;
}) {
  const router = useRouter();
  const [partes, setPartes] = useState<string[]>([item.texto_original, ""]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validas = partes.map((p) => p.trim()).filter(Boolean);
  const puedeDividir = validas.length >= 2;

  async function dividir() {
    if (!puedeDividir) {
      setError("Escribí al menos dos partes para dividir el renglón.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      for (const texto of validas) {
        await agregarItemLista(versionId, { texto_original: texto, cantidad: item.cantidad });
      }
      await quitarItemLista(versionId, item.id);
      onListo();
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo dividir el renglón.");
      setGuardando(false);
    }
  }

  return (
    <div className={styles.altaItem}>
      {partes.map((parte, i) => (
        <label key={i} className={styles.campo}>
          <span>Parte {i + 1}</span>
          <input
            value={parte}
            onChange={(e) =>
              setPartes((ps) => ps.map((p, j) => (j === i ? e.target.value : p)))
            }
            placeholder="Ej. 1 cuaderno cuadriculado grande"
            disabled={guardando}
          />
        </label>
      ))}
      {error ? <p className={styles.itemError}>{error}</p> : null}
      <div className={styles.itemAcciones}>
        <button
          type="button"
          className={styles.botonMini}
          onClick={() => setPartes((ps) => [...ps, ""])}
          disabled={guardando}
        >
          + Otra parte
        </button>
        <button
          type="button"
          className={styles.principal}
          onClick={dividir}
          disabled={guardando || !puedeDividir}
        >
          {guardando ? "Dividiendo…" : `Dividir en ${validas.length}`}
        </button>
      </div>
    </div>
  );
}
