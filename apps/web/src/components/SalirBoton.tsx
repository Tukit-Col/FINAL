"use client";

// Cierra la sesion: DELETE /api/sesion borra la cookie httpOnly (el cliente no
// puede borrarla solo) y luego refresca para que el servidor vuelva a leer un
// estado sin sesion. Se aisla en su propio componente para que las paginas de
// servidor que lo usan no tengan que volverse de cliente.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import styles from "./SalirBoton.module.css";

export default function SalirBoton({ className }: { className?: string }) {
  const router = useRouter();
  const [saliendo, setSaliendo] = useState(false);

  async function salir() {
    setSaliendo(true);
    try {
      await fetch("/api/sesion", { method: "DELETE" });
      router.replace("/");
      router.refresh();
    } finally {
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
