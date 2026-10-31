"use client";

// La dirección del checkout, con sugerencias de Google Places (New) cuando hay
// llave (ADR 0044). Sin llave, o si Google falla o rechaza la llave, es un
// campo de texto libre como siempre: Maps jamás bloquea el pago.
//
// Costo: un `AutocompleteSessionToken` por búsqueda, que se cierra con UN
// `fetchFields` al elegir —solo `formattedAddress` y `addressComponents`,
// campos Essentials— y se renueva después. Escribir sin elegir no cierra la
// sesión ni pide detalles.
//
// Combobox ARIA, como el buscador de colegio de `/empezar`: el foco se queda en
// el campo, las flechas mueven la opción activa (`aria-activedescendant`),
// Enter elige y Escape cierra la lista.

import { useEffect, useId, useRef, useState } from "react";
import { direccionDesdeComponentes, type DireccionDerivada } from "@tukit/contrato";
import { crearTurnos, esRechazoDePermisos } from "@/lib/direccion-checkout";
import { alRechazarLlave, cargarPlaces, llaveFueRechazada, rechazarLlave } from "@/lib/places";
import styles from "./Kits.module.css";

const MINIMO_CARACTERES = 3;
const ESPERA_MS = 250;
// Sesgo, no restricción: se sugiere primero Bogotá sin impedir una dirección de
// Soacha o Chía. 30 km desde el centro cubren las 20 localidades urbanas.
const SESGO_BOGOTA = { center: { lat: 4.6533, lng: -74.0836 }, radius: 30_000 };

export interface LugarElegido extends DireccionDerivada {
  direccion: string;
  google_place_id: string | null;
}

interface Sugerencia {
  principal: string;
  secundario: string;
  prediccion: google.maps.places.PlacePrediction;
}

interface Props {
  llave: string | null;
  valor: string;
  // Texto escrito a mano: quien lo recibe descarta el `place_id` anterior.
  onEscribir: (texto: string) => void;
  onElegir: (lugar: LugarElegido) => void;
}

export default function CampoDireccion({ llave, valor, onEscribir, onElegir }: Props) {
  const idBase = useId();
  const idLista = `${idBase}-lista`;
  const [places, setPlaces] = useState<google.maps.PlacesLibrary | null>(null);
  const [sugerencias, setSugerencias] = useState<Sugerencia[]>([]);
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const tokenRef = useRef<google.maps.places.AutocompleteSessionToken | null>(null);
  // Qué respuesta de Google todavía vale y la espera entre teclas
  // (`direccion-checkout.ts`).
  const [turnos] = useState(() => crearTurnos(ESPERA_MS));

  useEffect(
    () =>
      alRechazarLlave(() => {
        setPlaces(null);
        setSugerencias([]);
      }),
    [],
  );
  useEffect(() => () => turnos.cerrar(), [turnos]);

  // Se carga al primer foco, no al pintar el checkout: quien no llega a la
  // dirección no descarga la librería.
  function preparar() {
    if (!llave || places || llaveFueRechazada()) return;
    cargarPlaces(llave).then((libreria) => {
      if (libreria && !llaveFueRechazada()) setPlaces(libreria);
    });
  }

  function pedirSugerencias(texto: string, libreria: google.maps.PlacesLibrary, turno: number) {
    tokenRef.current ??= new libreria.AutocompleteSessionToken();
    libreria.AutocompleteSuggestion.fetchAutocompleteSuggestions({
      input: texto,
      sessionToken: tokenRef.current,
      includedRegionCodes: ["co"],
      locationBias: SESGO_BOGOTA,
      language: "es",
      region: "co",
    })
      .then(({ suggestions }) => {
        if (!turnos.vigente(turno)) return;
        setSugerencias(
          suggestions.flatMap(({ placePrediction: p }) =>
            p
              ? [
                  {
                    principal: p.mainText?.text ?? p.text.text,
                    secundario: p.secondaryText?.text ?? "",
                    prediccion: p,
                  },
                ]
              : [],
          ),
        );
        setActiva(0);
      })
      .catch((error: unknown) => {
        // Sin permisos (la API no está habilitada para la llave) no hay
        // reintento que valga: el campo pasa a manual y vuelve el
        // autocompletado del navegador. Otro error espera a la siguiente tecla.
        if (esRechazoDePermisos(error)) rechazarLlave();
        else if (turnos.vigente(turno)) setSugerencias([]);
      });
  }

  function escribir(texto: string) {
    onEscribir(texto);
    setAbierta(true);
    if (!places || texto.trim().length < MINIMO_CARACTERES) {
      turnos.teclear();
      setSugerencias([]);
      return;
    }
    const libreria = places;
    turnos.teclear((turno) => pedirSugerencias(texto.trim(), libreria, turno));
  }

  async function elegir(sugerencia: Sugerencia) {
    setAbierta(false);
    setSugerencias([]);
    // Cancela la búsqueda que esperaba y abre el turno de los detalles: si el
    // acudiente sigue escribiendo mientras llegan, lo que escribió gana.
    const turno = turnos.elegir();
    const textoSugerido = [sugerencia.principal, sugerencia.secundario].filter(Boolean).join(", ");
    const lugar = sugerencia.prediccion.toPlace();
    // El `fetchFields` cierra la sesión: la siguiente búsqueda estrena token.
    tokenRef.current = null;
    try {
      await lugar.fetchFields({ fields: ["formattedAddress", "addressComponents"] });
      if (!turnos.vigente(turno)) return;
      onElegir({
        direccion: lugar.formattedAddress || textoSugerido,
        google_place_id: lugar.id || null,
        ...direccionDesdeComponentes(lugar.addressComponents),
      });
    } catch {
      // Sin detalles no hay nada que pre-llenar: queda el texto sugerido y el
      // acudiente completa ciudad y localidad a mano.
      if (turnos.vigente(turno)) onEscribir(textoSugerido);
    }
  }

  const visible = abierta && sugerencias.length > 0;
  const indiceActivo = Math.min(activa, Math.max(sugerencias.length - 1, 0));

  function teclear(evento: React.KeyboardEvent<HTMLInputElement>) {
    if (!visible) return;
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      const paso = evento.key === "ArrowDown" ? 1 : -1;
      setActiva((indiceActivo + paso + sugerencias.length) % sugerencias.length);
    } else if (evento.key === "Enter") {
      // Enter con la lista abierta elige; nunca manda el pago a medias.
      evento.preventDefault();
      void elegir(sugerencias[indiceActivo]);
    } else if (evento.key === "Escape") {
      evento.preventDefault();
      setAbierta(false);
    }
  }

  return (
    <div className={styles.campoDireccion}>
      {/* Rótulo explícito y no envolvente: la lista de sugerencias no puede
          formar parte del nombre accesible del campo. */}
      <label htmlFor={`${idBase}-campo`}>Dirección</label>
      <input
        id={`${idBase}-campo`}
        value={valor}
        required
        autoComplete={places ? "off" : "street-address"}
        role={places ? "combobox" : undefined}
        aria-autocomplete={places ? "list" : undefined}
        aria-expanded={places ? visible : undefined}
        aria-controls={places ? idLista : undefined}
        aria-activedescendant={visible ? `${idLista}-${indiceActivo}` : undefined}
        onFocus={preparar}
        onBlur={() => setAbierta(false)}
        onChange={(e) => escribir(e.target.value)}
        onKeyDown={teclear}
      />
      {places && (
        <div className={styles.sugerenciasDireccion} hidden={!visible}>
          <ul id={idLista} role="listbox" aria-label="Direcciones sugeridas">
            {sugerencias.map((s, i) => (
              <li
                key={`${s.prediccion.placeId}-${i}`}
                id={`${idLista}-${i}`}
                role="option"
                aria-selected={i === indiceActivo}
                className={`${styles.sugerenciaDireccion} ${i === indiceActivo ? styles.sugerenciaActiva : ""}`}
                // `mousedown` y no `click`: el `blur` del campo cerraría la
                // lista antes de que el clic llegue a la opción.
                onMouseDown={(e) => {
                  e.preventDefault();
                  void elegir(s);
                }}
                onMouseEnter={() => setActiva(i)}
              >
                <span className={styles.sugerenciaPrincipal}>{s.principal}</span>
                {s.secundario && <span className={styles.sugerenciaSecundaria}>{s.secundario}</span>}
              </li>
            ))}
          </ul>
          {/* Atribución obligatoria de Google al mostrar sugerencias sin mapa. */}
          <p className={styles.atribucionGoogle} translate="no">
            Google Maps
          </p>
        </div>
      )}
    </div>
  );
}
