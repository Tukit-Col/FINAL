"use client";

import { useEffect } from "react";
import Link from "next/link";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { ATRIBUCION } from "@/lib/geocodificador";
import type { Marcador } from "@/lib/consolidado";
import styles from "./MapaEntregas.module.css";

const CENTRO_POR_OMISION: [number, number] = [4.711, -74.0721];

function icono(cantidad: number): L.DivIcon {
  return L.divIcon({
    className: styles.pin,
    html: `<span>${cantidad}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -14],
  });
}

function AjustarVista({ marcadores }: { marcadores: readonly Marcador[] }) {
  const mapa = useMap();
  useEffect(() => {
    if (marcadores.length === 0) return;
    const limites = L.latLngBounds(marcadores.map((m) => [m.punto.lat, m.punto.lon] as [number, number]));
    mapa.fitBounds(limites, { padding: [40, 40], maxZoom: 15 });
  }, [mapa, marcadores]);
  return null;
}

export default function MapaEntregas({ marcadores }: { marcadores: readonly Marcador[] }) {
  return (
    <MapContainer
      center={CENTRO_POR_OMISION}
      zoom={11}
      scrollWheelZoom={false}
      className={styles.mapa}
      aria-label="Mapa de entregas pendientes"
    >
      <TileLayer
        attribution={`&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors`}
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />
      <AjustarVista marcadores={marcadores} />
      {marcadores.map((m) => (
        <Marker
          key={`${m.colegio}-${m.punto.lat}-${m.punto.lon}`}
          position={[m.punto.lat, m.punto.lon]}
          icon={icono(m.entregas.length)}
        >
          <Popup>
            <strong>{m.colegio}</strong>
            <ul className={styles.popup}>
              {m.entregas.map((e) => (
                <li key={e.pedido_id}>
                  <Link href={`/logistica/${e.pedido_id}`}>{e.pedido_id.slice(0, 8).toUpperCase()}</Link> ·{" "}
                  {e.destinatario}
                  <br />
                  <span>{e.direccion}</span>
                </li>
              ))}
            </ul>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

export { ATRIBUCION };
