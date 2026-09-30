"use client";

// Cierra la sesion: DELETE /api/sesion borra la cookie httpOnly (el cliente no
// puede borrarla solo) y luego una navegacion completa a la home obliga al
// servidor a releer un estado sin sesion. Se aisla en su propio componente para
// que las paginas de servidor que lo usan no tengan que volverse de cliente.

import { useState } from "react";
import { LogOut } from "lucide-react";
import styles from "./SalirBoton.module.css";

export default function SalirBoton({ className }: { className?: string }) {
  const [saliendo, setSaliendo] = useState(false);

  async function salir() {
    setSaliendo(true);
    try {
      await fetch("/api/sesion", { method: "DELETE" });
      // Navegacion completa a la home: sin carrera replace/refresh, limpia el
      // estado de cliente y el servidor vuelve a leer una sesion ausente, de modo
      // que la Cabecera (Server Component del layout) se repinta en "Ingresar".
      // La regla sugiere router.push para rutas internas, pero aqui queremos
      // justamente la recarga completa (deja atras el arbol logueado), no una
      // navegacion cliente que reutilizaria el estado que buscamos tirar.
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
