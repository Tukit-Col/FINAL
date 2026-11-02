"use client";

// `ssr: false` solo se permite en componentes de cliente: este envoltorio es el
// que importa el Server Component de la pagina. Mientras Leaflet carga se pinta
// un recuadro del mismo tamano para que la pagina no salte.

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
