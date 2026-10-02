"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatearPesos, type ResultadoPago as Resultado } from "@tukit/contrato";
import { FalloApi, sincronizarPago } from "@/lib/api-navegador";
import styles from "../Pago.module.css";

const INTERVALO_MS = 3000;
const MAX_INTENTOS = 20;
const ESTADOS_REINTENTABLES = [502, 503, 504];

type Vista =
  | { tipo: "cargando" }
  | { tipo: "resultado"; datos: Resultado }
  | { tipo: "reintento"; mensaje: string }
  | { tipo: "agotado" }
  | { tipo: "error"; mensaje: string };

export default function ResultadoPago({ id }: { id: string | undefined }) {
  const [vista, setVista] = useState<Vista>({ tipo: "cargando" });

  useEffect(() => {
    if (!id) return;
    let vivo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function consultar(intento: number) {
      let siguiente: Vista;
      let reintentar = false;
      try {
        const datos = await sincronizarPago(id as string);
        siguiente = { tipo: "resultado", datos };
        reintentar = datos.estado_pago === "iniciado";
      } catch (causa) {
        if (causa instanceof FalloApi && ESTADOS_REINTENTABLES.includes(causa.estado)) {
          siguiente = { tipo: "reintento", mensaje: "No pudimos confirmar todavía" };
          reintentar = true;
        } else {
          siguiente = {
            tipo: "error",
            mensaje:
              causa instanceof FalloApi ? causa.message : "No pudimos confirmar tu pago.",
          };
        }
      }
      if (!vivo) return;
      if (reintentar && intento >= MAX_INTENTOS) {
        setVista({ tipo: "agotado" });
        return;
      }
      setVista(siguiente);
      if (reintentar) timer = setTimeout(() => void consultar(intento + 1), INTERVALO_MS);
    }

    void consultar(1);
    return () => {
      vivo = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  const panel = (
    <Link href="/dashboard" className={styles.pagar}>
      Ir a mi panel
    </Link>
  );

  let contenido: React.ReactNode;
  if (!id) {
    contenido = (
      <>
        <p className={styles.titulo}>No encontramos el pago que intentas ver.</p>
        <div className={styles.acciones}>{panel}</div>
      </>
    );
  } else if (vista.tipo === "cargando") {
    contenido = <p className={styles.titulo}>Estamos confirmando tu pago…</p>;
  } else if (vista.tipo === "reintento") {
    contenido = (
      <>
        <p className={styles.titulo}>{vista.mensaje}</p>
        <p className={styles.texto}>Estamos reintentando…</p>
      </>
    );
  } else if (vista.tipo === "agotado") {
    contenido = (
      <>
        <p className={styles.titulo}>Aún no tenemos la confirmación de tu pago. Vuelve a abrir esta página en unos minutos o revisa tu panel.</p>
        <div className={styles.acciones}>{panel}</div>
      </>
    );
  } else if (vista.tipo === "error") {
    contenido = (
      <>
        <p className={`${styles.titulo} ${styles.error}`}>{vista.mensaje}</p>
        <div className={styles.acciones}>{panel}</div>
      </>
    );
  } else {
    const { datos } = vista;
    switch (datos.estado_pago) {
      case "aprobado":
        contenido = (
          <>
            <h1 className={styles.titulo}>¡Pago aprobado!</h1>
            <span className={`${styles.total} cifra`}>{formatearPesos(datos.total)}</span>
            <p className={styles.texto}>Pedido {datos.pedido_id.slice(0, 8)}</p>
            <div className={styles.acciones}>{panel}</div>
          </>
        );
        break;
      case "rechazado":
        contenido = (
          <>
            <h1 className={styles.titulo}>Tu pago no fue aprobado</h1>
            <p className={styles.texto}>
              No se hizo ningún cobro. Puedes intentarlo de nuevo.
            </p>
            <div className={styles.acciones}>
              {datos.trabajo_id ? (
                <Link href={`/kits/${datos.trabajo_id}`} className={styles.pagar}>
                  Volver a mi kit
                </Link>
              ) : (
                panel
              )}
            </div>
          </>
        );
        break;
      case "reembolsado":
        contenido = (
          <>
            <h1 className={styles.titulo}>Este pago fue reembolsado.</h1>
            <div className={styles.acciones}>{panel}</div>
          </>
        );
        break;
      case "iniciado":
        contenido = <p className={styles.titulo}>Estamos confirmando tu pago…</p>;
        break;
    }
  }

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta} role="status" aria-live="polite">
        {contenido}
      </div>
    </div>
  );
}
