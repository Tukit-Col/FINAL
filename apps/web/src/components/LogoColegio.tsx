"use client";

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
