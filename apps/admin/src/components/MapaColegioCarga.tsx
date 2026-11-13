"use client";

// `ssr: false` solo se permite en componentes de cliente: este envoltorio carga
// el mapa (Leaflet) en el navegador.

import dynamic from "next/dynamic";
import type { Punto } from "@/lib/geocodificador";

const MapaColegio = dynamic(() => import("./MapaColegio"), { ssr: false });

export default function MapaColegioCarga({ punto, nombre }: { punto: Punto; nombre: string }) {
  return <MapaColegio punto={punto} nombre={nombre} />;
}
