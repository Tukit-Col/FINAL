// 404 de la consola. Dentro del layout: con sesion la cabecera (y el logo) ya está arriba.

import Link from "next/link";

export default function NoEncontrada() {
  return (
    <section style={{ padding: 24 }}>
      <h1>No encontramos esa página</h1>
      <p>La dirección está incompleta o ya no existe en la consola.</p>
      <Link href="/">Volver al panel</Link>
    </section>
  );
}
