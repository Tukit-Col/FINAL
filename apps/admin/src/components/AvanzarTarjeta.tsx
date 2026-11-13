"use client";

// El boton de avance de una tarjeta del tablero. Envia SOLO el paso natural
// que la matriz de `lib/logistica.ts` permite desde el estado (via
// `accionDeTarjeta`), por el mismo endpoint que el detalle (`avanzarPedido`).
// No hay arrastrar y soltar: un boton es accesible por teclado y no deja
// soltar un pedido en una etapa ilegal.
//
// Los pasos que piden datos (despachar: repartidor) no se envian desde aqui:
// el boton lleva al formulario del detalle. Si comercio responde 409 (otro
// operador lo movio), se refresca el tablero y el pedido aparece donde esta.

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { EstadoPedido } from "@tukit/contrato";
import { avanzarPedido, FalloApi } from "@/lib/api-navegador";
import { accionDeTarjeta } from "@/lib/logistica";
import BannerAcceso, { type FalloVisible } from "./BannerAcceso";
import styles from "./TableroPedidos.module.css";

interface Props {
  pedidoId: string;
  estado: EstadoPedido;
  /** El codigo corto, para que el nombre accesible diga QUE pedido se mueve. */
  codigo: string;
  urlIngresar?: string;
}

export default function AvanzarTarjeta({ pedidoId, estado, codigo, urlIngresar }: Props) {
  const router = useRouter();
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<FalloVisible | null>(null);
  const paso = accionDeTarjeta(estado);
  if (!paso) return null;
  const { accion, directa } = paso;

  if (!directa) {
    return (
      <Link
        href={`/logistica/${pedidoId}#acciones-titulo`}
        className={styles.avanzar}
        aria-label={`${accion.etiqueta} el pedido ${codigo} (abre el detalle)`}
      >
        {accion.etiqueta}…
      </Link>
    );
  }

  async function avanzar(): Promise<void> {
    setFallo(null);
    setEnviando(true);
    try {
      await avanzarPedido(pedidoId, { destino: accion.destino });
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setFallo({ estado: causa.estado, mensaje: causa.message });
        if (causa.estado === 409) router.refresh();
      } else {
        setFallo({ estado: 0, mensaje: "No pudimos mover el pedido. Intenta de nuevo." });
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className={styles.avanzar}
        disabled={enviando}
        aria-label={`${accion.etiqueta}: pedido ${codigo}`}
        onClick={() => void avanzar()}
      >
        {enviando ? "Moviendo…" : accion.etiqueta}
      </button>
      <BannerAcceso fallo={fallo} urlIngresar={urlIngresar} onCerrar={() => setFallo(null)} />
    </>
  );
}
