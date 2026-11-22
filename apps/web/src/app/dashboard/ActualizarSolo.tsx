"use client";

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
