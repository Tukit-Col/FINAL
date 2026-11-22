"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CreditCard, RefreshCw, X } from "lucide-react";
import { FalloApi, cancelarPedido, pagarPedido } from "@/lib/api-navegador";
import { abrirWidgetWompi } from "@/lib/wompi";
import styles from "./Dashboard.module.css";

export default function AccionesPedido({
  pedidoId,
  trabajoId,
  vencido,
}: {
  pedidoId: string;
  trabajoId: string | null;
  vencido: boolean;
}) {
  const router = useRouter();
  const [ocupado, setOcupado] = useState<"pagar" | "cancelar" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pagar() {
    setOcupado("pagar");
    setError(null);
    try {
      const pago = await pagarPedido(pedidoId);
      if (pago.widget) {
        await abrirWidgetWompi(pago.widget, (transaccionId) => {
          router.push(`/pago/resultado?id=${encodeURIComponent(transaccionId)}`);
        });
        setOcupado(null);
      } else if (pago.url_redireccion) {
        window.location.href = pago.url_redireccion;
      } else {
        setError("No pudimos abrir la pasarela de pago.");
        setOcupado(null);
      }
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos iniciar el pago.");
      setOcupado(null);
    }
  }

  async function cancelar() {
    const seguro = window.confirm(
      "¿Cancelar este pedido? Liberaremos los productos reservados y no podrás pagarlo después.",
    );
    if (!seguro) return;
    setOcupado("cancelar");
    setError(null);
    try {
      await cancelarPedido(pedidoId);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos cancelar el pedido.");
      router.refresh();
    } finally {
      setOcupado(null);
    }
  }

  return (
    <div className={vencido ? `${styles.franja} ${styles.franjaVencida}` : styles.franja}>
      <div className={styles.franjaTexto}>
        <span>
          {vencido
            ? "Pasaron más de 24 horas. Arma el kit de nuevo para ver el precio de hoy."
            : "Este pedido está esperando tu pago."}
        </span>
        {error && (
          <span className={styles.errorPedido} role="alert">
            {error}
          </span>
        )}
      </div>
      <div className={styles.accionesFila}>
        {vencido ? (
          trabajoId && (
            <Link href={`/kits/${trabajoId}`} className={styles.btnRearmar}>
              <RefreshCw size={14} aria-hidden /> Rearmar kit
            </Link>
          )
        ) : (
          <button
            type="button"
            className={styles.btnPagar}
            onClick={pagar}
            disabled={ocupado !== null}
          >
            <CreditCard size={14} aria-hidden />
            {ocupado === "pagar" ? "Abriendo…" : "Pagar"}
          </button>
        )}
        <button
          type="button"
          className={styles.btnCancelar}
          onClick={cancelar}
          disabled={ocupado !== null}
        >
          <X size={14} aria-hidden />
          {ocupado === "cancelar" ? "Cancelando…" : "Cancelar"}
        </button>
      </div>
    </div>
  );
}
