"use client";

// Cierra la sesion del back-office: DELETE /api/sesion borra la cookie httpOnly
// (el cliente no puede borrarla solo) y devuelve a donde volver —el login de la
// web (:3000)—. El salto es a OTRO origen, asi que se usa `window.location` y no
// el router de Next. Se aisla en su propio componente de cliente para que la
// cabecera pueda seguir siendo tan de servidor como quiera el resto.

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
      // El destino lo decide el servidor (otro origen). Si por lo que sea no
      // llega, recargar deja igualmente al usuario fuera: la cookie ya no esta.
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
