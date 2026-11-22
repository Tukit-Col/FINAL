"use client";

import dynamic from "next/dynamic";
import type { Punto } from "@/lib/geocodificador";

const MapaColegio = dynamic(() => import("./MapaColegio"), { ssr: false });

export default function MapaColegioCarga({ punto, nombre }: { punto: Punto; nombre: string }) {
  return <MapaColegio punto={punto} nombre={nombre} />;
}
