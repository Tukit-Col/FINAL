"use client";

// Las acciones de un pedido pendiente en "Mis pedidos":
// - Pagar: abre el mismo widget de Wompi que el kit, sobre un intento de pago
//   nuevo del pedido. Al terminar va a la pantalla de resultado.
// - Cancelar: pide confirmacion; Comercio pregunta a Wompi antes y no cancela
//   si hay un pago aprobado o en curso (su mensaje se muestra tal cual).
// - Vencido (mas de 24 horas): ya no se paga; se ofrece volver a armar el kit,
//   donde el precio se re-verifica. Cancelarlo libera lo reservado.

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
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
      // Un 409 puede significar que el pago ya se aprobo: refrescar muestra el
      // estado real del pedido.
      router.refresh();
    } finally {
      setOcupado(null);
    }
  }

  return (
    <div className={styles.accionPedido}>
      <div className={styles.accionesFila}>
        {vencido ? (
          <span className={styles.vencido}>
            Vencido
            {trabajoId && (
              <>
                {" · "}
                <Link href={`/kits/${trabajoId}`} className={styles.rearmar}>
                  Volver a armar el kit
                </Link>
              </>
            )}
          </span>
        ) : (
          <button
            type="button"
            className={styles.btnPagar}
            onClick={pagar}
            disabled={ocupado !== null}
          >
            {ocupado === "pagar" ? "Abriendo…" : "Pagar"}
          </button>
        )}
        <button
          type="button"
          className={styles.btnCancelar}
          onClick={cancelar}
          disabled={ocupado !== null}
        >
          {ocupado === "cancelar" ? "Cancelando…" : "Cancelar"}
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
