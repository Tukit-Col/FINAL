// Logo de la marca (libro-tienda + nombre) para las pantallas que no llevan la
// cabecera del back-office: aviso sin sesion y error global. Tamaño fijo en
// width/height, así no hay salto de layout.

import Image from "next/image";

export default function MarcaTukit() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
      <Image src="/marca/logo.png" alt="TUKIT" width={34} height={30} priority />
      <span style={{ fontWeight: 800, fontSize: 20 }} aria-hidden="true">
        Tukit
      </span>
    </div>
  );
}
