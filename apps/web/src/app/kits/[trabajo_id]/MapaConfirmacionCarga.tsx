"use client";

// `ssr: false` solo se permite en componentes de cliente, y Leaflet toca `window`
// al importarse: por eso el mapa se carga aquí, en el navegador, y solo cuando el
// acudiente ya eligió una dirección (quien no llega ahí no descarga Leaflet).
// Mientras carga se pinta un recuadro del mismo tamaño para que no salte la página.

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
