"use client";

import dynamic from "next/dynamic";
import type { Marcador } from "@/lib/consolidado";
import styles from "./MapaEntregas.module.css";

const MapaEntregas = dynamic(() => import("./MapaEntregas"), {
  ssr: false,
  loading: () => <div className={styles.cargando}>Cargando mapa…</div>,
});

export default function MapaEntregasCarga({ marcadores }: { marcadores: readonly Marcador[] }) {
  return <MapaEntregas marcadores={marcadores} />;
}
