"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import styles from "./SalirBoton.module.css";

export default function SalirBoton({ className }: { className?: string }) {
  const [saliendo, setSaliendo] = useState(false);

  async function salir() {
    setSaliendo(true);
    try {
      await fetch("/api/sesion", { method: "DELETE" });
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/");
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
