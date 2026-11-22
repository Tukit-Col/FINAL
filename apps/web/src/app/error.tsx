"use client";

export default function ErrorDeRuta({ reset }: { error: Error; reset: () => void }) {
  return (
    <section role="alert" style={{ maxWidth: 560, margin: "0 auto", padding: "64px 24px" }}>
      <h1>Algo salió mal</h1>
      <p>No pudimos cargar esta página. Intenta de nuevo en un momento.</p>
      <button type="button" onClick={reset}>
        Reintentar
      </button>
    </section>
  );
}
