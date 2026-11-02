import Link from "next/link";

export default function TicketNoEncontrado() {
  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h1>No encontramos ese ticket</h1>
      <p>El código no existe o está mal escrito.</p>
      <Link href="/tickets">← Volver a tickets</Link>
    </section>
  );
}
