"use client";

import dynamic from "next/dynamic";
import styles from "./Kits.module.css";

const MapaConfirmacion = dynamic(() => import("./MapaConfirmacion"), {
  ssr: false,
  loading: () => <div className={styles.mapaCargando}>Cargando mapa…</div>,
});

export default function MapaConfirmacionCarga(props: {
  latitud: number;
  longitud: number;
  onMover: (latitud: number, longitud: number) => void;
}) {
  return <MapaConfirmacion {...props} />;
}
