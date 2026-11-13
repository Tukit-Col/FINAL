"use client";

// Mantiene al dia "Mis pedidos" sin que el padre recargue: mientras la pestana
// esta visible repite la lectura del servidor cada 30 s (`router.refresh()`,
// que solo trae los datos nuevos) y la repite al volver a la pestana. Con la
// pestana oculta no pide nada, y dos lecturas nunca quedan a menos de 10 s.
// No pinta nada: el dato nuevo llega por el mismo Server Component.

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const CADA_MS = 30_000;
const MINIMO_MS = 10_000;

export default function ActualizarSolo({ activo }: { activo: boolean }) {
  const router = useRouter();
  const ultima = useRef(0);

  useEffect(() => {
    if (!activo) return;
    ultima.current = Date.now();
    const leer = () => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - ultima.current < MINIMO_MS) return;
      ultima.current = Date.now();
      router.refresh();
    };
    const reloj = window.setInterval(leer, CADA_MS);
    document.addEventListener("visibilitychange", leer);
    window.addEventListener("focus", leer);
    return () => {
      window.clearInterval(reloj);
      document.removeEventListener("visibilitychange", leer);
      window.removeEventListener("focus", leer);
    };
  }, [activo, router]);

  return null;
}
