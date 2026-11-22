"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { type ItemListaEditable } from "@tukit/contrato";
import { agregarItemLista, FalloListas } from "@/lib/api-listas";
import styles from "@/app/onboarding/Onboarding.module.css";

export default function AltaRenglon({ versionId, revisada }: { versionId: string; revisada: boolean }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function agregar() {
    setGuardando(true);
    setError(null);
    const item: ItemListaEditable = { texto_original: texto.trim() };
    const cantidadNum = Number(cantidad);
    if (Number.isFinite(cantidadNum)) item.cantidad = cantidadNum;
    try {
      await agregarItemLista(versionId, item);
      setTexto("");
      setCantidad("1");
      setAbierto(false);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo agregar el ítem.");
    } finally {
      setGuardando(false);
    }
  }

  if (!abierto) {
    return (
      <button
        type="button"
        className={styles.botonMini}
        onClick={() => setAbierto(true)}
        disabled={revisada}
      >
        + Agregar un ítem que faltó
      </button>
    );
  }

  return (
    <div className={styles.altaItem}>
      <label className={styles.campo}>
        <span>Texto del renglón</span>
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Ej. 2 cuadernos cuadriculados grandes"
          disabled={guardando}
        />
      </label>
      <label className={styles.campo}>
        <span>Cantidad</span>
        <input
          type="number"
          min={0}
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          disabled={guardando}
        />
      </label>
      {error ? <p className={styles.itemError}>{error}</p> : null}
      <div className={styles.itemAcciones}>
        <button
          type="button"
          className={styles.principal}
          onClick={agregar}
          disabled={guardando || !texto.trim()}
        >
          {guardando ? "Agregando…" : "Agregar ítem"}
        </button>
        <button type="button" className={styles.botonMini} onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
