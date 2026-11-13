"use client";

// El mapita de la ficha del colegio: un pin en su direccion. Solo navegador (lo
// importa `MapaColegioCarga` con `ssr: false`) porque Leaflet toca `window`. El
// punto ya viene geocodificado del servidor (Nominatim con cache en disco).

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import type { Punto } from "@/lib/geocodificador";
import styles from "./MapaEntregas.module.css";

const PIN = L.divIcon({ className: styles.pin, html: "<span>•</span>", iconSize: [30, 30] });

export default function MapaColegio({ punto, nombre }: { punto: Punto; nombre: string }) {
  return (
    <MapContainer
      center={[punto.lat, punto.lon]}
      zoom={16}
      scrollWheelZoom={false}
      className={styles.mapa}
      aria-label={`Ubicación de ${nombre}`}
    >
      <TileLayer
        attribution={`&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors`}
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />
      <Marker position={[punto.lat, punto.lon]} icon={PIN} />
    </MapContainer>
  );
}
