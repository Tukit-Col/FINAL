"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import styles from "./SalirBoton.module.css";

export default function SalirBoton({ className }: { className?: string }) {
  const [saliendo, setSaliendo] = useState(false);

  async function salir() {
    setSaliendo(true);
    try {
      const respuesta = await fetch("/api/sesion", { method: "DELETE" });
      const destino = (await respuesta.json().catch(() => null)) as { url?: string } | null;
      window.location.href = destino?.url ?? "/";
    } catch {
      setSaliendo(false);
    }
  }

  return (
    <button
      type="button"
      onClick={salir}
      disabled={saliendo}
      className={`${styles.salir} ${className ?? ""}`}
    >
      <LogOut size={15} strokeWidth={2.4} aria-hidden="true" />
      {saliendo ? "Saliendo…" : "Cerrar sesión"}
    </button>
  );
}
