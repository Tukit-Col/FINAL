"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { dentroDeColombia } from "@/lib/direccion-osm";
import styles from "./Kits.module.css";

const PASO_GRADOS = 0.0001;

interface Props {
  latitud: number;
  longitud: number;
  onMover: (latitud: number, longitud: number) => void;
}

export default function MapaConfirmacion({ latitud, longitud, onMover }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const pin = useRef<L.Marker | null>(null);
  const alMover = useRef(onMover);
  useEffect(() => {
    alMover.current = onMover;
  }, [onMover]);

  useEffect(() => {
    if (!contenedor.current) return;
    const nuevo = L.map(contenedor.current, {
      center: [latitud, longitud],
      zoom: 17,
      scrollWheelZoom: false,
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(nuevo);

    const marcador = L.marker([latitud, longitud], {
      draggable: true,
      keyboard: true,
      title: "Arrastra el pin hasta tu puerta",
      icon: L.divIcon({
        className: styles.pinEntrega,
        html: "<span></span>",
        iconSize: [34, 34],
        iconAnchor: [17, 34],
      }),
    }).addTo(nuevo);

    let ultimoValido = L.latLng(latitud, longitud);
    function mover(destino: L.LatLng) {
      if (!dentroDeColombia(destino.lat, destino.lng)) {
        marcador.setLatLng(ultimoValido);
        return;
      }
      ultimoValido = destino;
      marcador.setLatLng(destino);
      alMover.current(destino.lat, destino.lng);
    }
    marcador.on("dragend", () => mover(marcador.getLatLng()));
    nuevo.on("click", (e: L.LeafletMouseEvent) => {
      mover(e.latlng);
      nuevo.panTo(e.latlng);
    });
    marcador.getElement()?.addEventListener("keydown", (e) => {
      const flechas: Record<string, [number, number]> = {
        ArrowUp: [PASO_GRADOS, 0],
        ArrowDown: [-PASO_GRADOS, 0],
        ArrowLeft: [0, -PASO_GRADOS],
        ArrowRight: [0, PASO_GRADOS],
      };
      const paso = flechas[(e as KeyboardEvent).key];
      if (!paso) return;
      e.preventDefault();
      e.stopPropagation();
      const actual = marcador.getLatLng();
      mover(L.latLng(actual.lat + paso[0], actual.lng + paso[1]));
    });

    mapa.current = nuevo;
    pin.current = marcador;
    return () => {
      nuevo.remove();
      mapa.current = null;
      pin.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const marcador = pin.current;
    const vista = mapa.current;
    if (!marcador || !vista) return;
    const destino = L.latLng(latitud, longitud);
    if (marcador.getLatLng().equals(destino, 1e-9)) return;
    marcador.setLatLng(destino);
    vista.setView(destino, Math.max(vista.getZoom(), 17));
  }, [latitud, longitud]);

  return (
    <div className={styles.confirmacionMapa}>
      <p className={styles.ayudaMapa}>
        Confirma el punto: arrastra el pin o toca el mapa donde queda tu puerta. Con teclado, enfoca el pin y muévelo con las flechas.
      </p>
      <div ref={contenedor} className={styles.mapaEntrega} role="group" aria-label="Mapa para confirmar la dirección de entrega" />
    </div>
  );
}
