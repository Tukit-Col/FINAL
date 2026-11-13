"use client";

// Último recurso: reemplaza el layout, así que no hay cabecera. Estilos en línea
// porque globals.css puede no haber cargado.

import Image from "next/image";

export default function ErrorGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="es">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 24, maxWidth: 560, margin: "0 auto" }}>
        <Image src="/marca/tukit-marca.webp" alt="TUKIT" width={64} height={72} priority />
        <h1>Tukit no pudo cargar</h1>
        <p>Reintenta en un momento.</p>
        <button type="button" onClick={reset}>
          Reintentar
        </button>
      </body>
    </html>
  );
}
