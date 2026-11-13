"use client";

// Error de una ruta de la consola. Dentro del layout: la cabecera con el logo sigue visible.

export default function ErrorDeRuta({ reset }: { error: Error; reset: () => void }) {
  return (
    <section role="alert" style={{ padding: 24 }}>
      <h1>Algo salió mal</h1>
      <p>No pudimos cargar esta pantalla. Intenta de nuevo; si sigue, revisa que los servicios estén arriba.</p>
      <button type="button" onClick={reset}>
        Reintentar
      </button>
    </section>
  );
}
