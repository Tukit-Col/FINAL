"use client";

// "Cancelar solicitud" en "Mis solicitudes": un botón discreto que pide
// confirmación en la misma tarjeta. Un trabajo se cancela en Inteligencia, que
// no deja cancelar un kit comprado ni uno con un pago pendiente (su mensaje se
// muestra tal cual); una lista subida que aún no tiene kit deja de ser del
// acudiente sin borrarse (ADR 0031).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { FalloApi, cancelarListaSubida, cancelarSolicitud } from "@/lib/api-navegador";
import styles from "./Dashboard.module.css";

export default function CancelarSolicitud(
  props: { trabajoId: string; tareaId?: undefined } | { tareaId: string; trabajoId?: undefined },
) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function cancelar() {
    setOcupado(true);
    setError(null);
    try {
      if (props.trabajoId) await cancelarSolicitud(props.trabajoId);
      else if (props.tareaId) await cancelarListaSubida(props.tareaId);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos cancelar la solicitud.");
      setOcupado(false);
    }
  }

  if (!confirmando) {
    return (
      <button
        type="button"
        className={`${styles.accionDiscreta} ${styles.accionDiscretaPeligro}`}
        onClick={() => setConfirmando(true)}
      >
        <X size={13} aria-hidden /> Cancelar solicitud
      </button>
    );
  }

  return (
    <div className={styles.confirmacion} role="alertdialog" aria-label="Cancelar solicitud">
      <p>
        {props.tareaId
          ? "¿Cancelar esta solicitud? Dejaremos de armarte un kit con esta lista."
          : "¿Cancelar esta solicitud? Ya no podrás ver ni pagar sus kits."}
      </p>
      <div className={styles.hijoAcciones}>
        <button type="button" className={styles.btnPeligro} disabled={ocupado} onClick={() => void cancelar()}>
          {ocupado ? "Cancelando…" : "Sí, cancelar"}
        </button>
        <button
          type="button"
          className={styles.btnCancelar}
          disabled={ocupado}
          onClick={() => {
            setConfirmando(false);
            setError(null);
          }}
        >
          No
        </button>
      </div>
      {error && (
        <span className={styles.errorPedido} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
