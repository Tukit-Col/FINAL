"use client";

// El logo de un colegio con su respaldo: si no hay URL, o la imagen no carga
// (enlace roto, sitio caido), se pintan las iniciales. La URL ya llega resuelta
// con la regla de `logoDeColegio` (Identidad primero, luego el directorio).
// `<img>` y no `next/image`: los logos viven en sitios de terceros que no estan
// en `images.remotePatterns`.

import { useState } from "react";
import { inicialesColegio } from "@tukit/contrato";

export default function LogoColegio({
  src,
  nombre,
  claseImagen,
  claseIniciales,
}: {
  src: string | null;
  nombre: string;
  claseImagen?: string;
  claseIniciales?: string;
}) {
  // Se recuerda QUE URL fallo, no un booleano: si cambia la URL se vuelve a intentar.
  const [fallida, setFallida] = useState<string | null>(null);
  if (src && src !== fallida) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img className={claseImagen} src={src} alt="" onError={() => setFallida(src)} />;
  }
  return (
    <span className={claseIniciales} aria-hidden="true">
      {inicialesColegio(nombre)}
    </span>
  );
}
