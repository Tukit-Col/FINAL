"use client";

// "Pagar" en Mis pedidos: abre el mismo widget de Wompi que el kit, sobre un
// intento de pago nuevo del pedido pendiente. Al terminar va a la pantalla de
// resultado, que confirma con el servidor.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FalloApi, pagarPedido } from "@/lib/api-navegador";
import { abrirWidgetWompi } from "@/lib/wompi";
import styles from "./Dashboard.module.css";

export default function BotonPagarPedido({ pedidoId }: { pedidoId: string }) {
  const router = useRouter();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pagar() {
    setEnviando(true);
    setError(null);
    try {
      const pago = await pagarPedido(pedidoId);
      if (pago.widget) {
        await abrirWidgetWompi(pago.widget, (transaccionId) => {
          router.push(`/pago/resultado?id=${encodeURIComponent(transaccionId)}`);
        });
        setEnviando(false);
      } else if (pago.url_redireccion) {
        window.location.href = pago.url_redireccion;
      } else {
        setError("No pudimos abrir la pasarela de pago.");
        setEnviando(false);
      }
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos iniciar el pago.");
      setEnviando(false);
    }
  }

  return (
    <div className={styles.accionPedido}>
      <button type="button" className={styles.btnPagar} onClick={pagar} disabled={enviando}>
        {enviando ? "Abriendo…" : "Pagar"}
      </button>
      {error && (
        <span className={styles.errorPedido} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
