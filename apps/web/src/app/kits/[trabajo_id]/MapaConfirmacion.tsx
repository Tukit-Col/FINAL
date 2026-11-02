"use client";

// El mapa donde el acudiente confirma el punto de entrega: OpenStreetMap con
// Leaflet y un pin que se arrastra o se mueve con un toque en el mapa. Solo corre
// en el navegador (lo importa `MapaConfirmacionCarga` con `ssr: false`).
//
// Se usa Leaflet directo y no `react-leaflet`: es un solo mapa con un solo pin, y
// así `apps/web` no suma una dependencia más. El pin es un `divIcon` y no la
// imagen por omisión de Leaflet, cuyas rutas de PNG se rompen al empaquetar.
//
// Accesibilidad: el pin recibe foco y se mueve con las flechas (unos 10 m por
// pulsación); sin mapa, la dirección escrita sigue valiendo.

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { dentroDeColombia } from "@/lib/direccion-osm";
import styles from "./Kits.module.css";

// ~11 m de latitud: lo bastante fino para acertar el portón, sin que cruzar una
// cuadra cueste cien pulsaciones.
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
  // El último `onMover`, sin recrear el mapa cada vez que el padre re-renderiza.
  const alMover = useRef(onMover);
  // Se actualiza en un efecto y no al renderizar: leer o escribir un ref durante
  // el render puede dejar el componente desfasado.
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
      // Atribución visible sobre el mapa, como exige la licencia de OSM.
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

    // Un punto fuera de Colombia no se acepta (Comercio lo rechazaría): el pin
    // vuelve donde estaba y el pago no se rompe por un arrastre torpe.
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
      // Que el mapa no se desplace además de mover el pin.
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
    // El mapa se crea una vez; los cambios de punto se aplican en el efecto de abajo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Si el punto cambia desde fuera (eligió otro resultado), el pin y la vista lo siguen.
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
