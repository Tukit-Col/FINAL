import Link from "next/link";

export default function NoEncontrada() {
  return (
    <section style={{ maxWidth: 560, margin: "0 auto", padding: "64px 24px" }}>
      <h1>No encontramos esa página</h1>
      <p>El enlace puede estar incompleto o la página ya no existe.</p>
      <Link href="/">Volver al inicio</Link>
    </section>
  );
}
