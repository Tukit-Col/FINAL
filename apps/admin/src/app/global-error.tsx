"use client";

import MarcaTukit from "@/components/MarcaTukit";

export default function ErrorGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="es">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
        <MarcaTukit />
        <h1>La consola no pudo cargar</h1>
        <p>Reintenta en un momento.</p>
        <button type="button" onClick={reset}>
          Reintentar
        </button>
      </body>
    </html>
  );
}
