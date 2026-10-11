"use client";

// El colegio de "Subir lista" en la cola. Reemplaza al `<select>` de los
// colegios de Tukit: el staff tiene que poder subir la lista de CUALQUIER
// colegio de Bogotá, aunque Tukit todavía no lo tenga. Mezcla, en este orden:
//   1. los colegios que Tukit ya conoce (aliados o no, marcados);
//   2. el directorio de Bogotá, con localidad, DANE y logo si lo hay;
//   3. "No lo encuentro: usar '…' tal cual".
// La búsqueda es la pura de `@tukit/contrato`, la misma de `/empezar`: una
// entrada del directorio cuyo DANE ya es de un colegio de Tukit se ofrece como
// ese colegio, para no duplicarlo al aprobar.
//
// Combobox ARIA: el foco se queda en el campo y las flechas mueven la opción
// activa (`aria-activedescendant`); Enter elige y Escape cierra la lista.

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Pencil, Search } from "lucide-react";
import {
  buscarColegios,
  imagenesPorDane,
  logoDeColegio,
  MINIMO_BUSQUEDA,
  normalizarBusqueda,
  prepararBusqueda,
  type Colegio,
  type ColegioDesignado,
  type EntradaDirectorio,
} from "@tukit/contrato";
import LogoColegio from "@/components/LogoColegio";
import styles from "@/app/onboarding/Onboarding.module.css";

// El directorio pesa ~300 KB: se pide al primer foco y una sola vez por carga.
let directorioPromesa: Promise<EntradaDirectorio[]> | null = null;
function cargarDirectorio(): Promise<EntradaDirectorio[]> {
  if (!directorioPromesa) {
    directorioPromesa = fetch("/directorio-colegios.json")
      .then((r) => (r.ok ? (r.json() as Promise<EntradaDirectorio[]>) : []))
      .catch(() => []);
  }
  return directorioPromesa;
}

interface Opcion {
  clave: string;
  designado: ColegioDesignado;
  nombre: string;
  detalle: string;
  logo: string | null;
  marca: string | null;
  escrito?: boolean;
}

interface Props {
  colegios: Colegio[];
  onElegir: (colegio: ColegioDesignado | null) => void;
}

export default function BuscadorColegioOnboarding({ colegios, onElegir }: Props) {
  const idBase = useId();
  const idLista = `${idBase}-lista`;
  const [directorio, setDirectorio] = useState<EntradaDirectorio[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const [elegida, setElegida] = useState<Opcion | null>(null);
  const campoRef = useRef<HTMLInputElement>(null);
  // "Cambiar" desaparece al pulsarlo: el foco vuelve al campo de búsqueda, que
  // se pinta en el render siguiente, y no se pierde en el `body`.
  const enfocarRef = useRef(false);

  useEffect(() => {
    if (elegida || !enfocarRef.current) return;
    enfocarRef.current = false;
    campoRef.current?.focus();
  }, [elegida]);

  const asegurarCargado = useCallback(() => {
    if (directorio.length === 0) cargarDirectorio().then(setDirectorio);
  }, [directorio.length]);

  const preparada = useMemo(() => prepararBusqueda(colegios, directorio), [colegios, directorio]);
  const imagenes = useMemo(() => imagenesPorDane(directorio), [directorio]);

  const consulta = busqueda.trim();
  const suficiente = normalizarBusqueda(consulta).length >= MINIMO_BUSQUEDA;
  const opciones = useMemo<Opcion[]>(() => {
    if (!suficiente) return [];
    const r = buscarColegios(preparada, consulta);
    return [
      ...r.colegios.map(({ colegio, etiqueta }) => ({
        clave: `tukit-${colegio.colegio_id}`,
        designado: { colegio_id: colegio.colegio_id },
        nombre: etiqueta,
        detalle: colegio.dane ? `DANE ${colegio.dane}` : "Sin DANE",
        logo: logoDeColegio(colegio, imagenes),
        marca: (colegio.es_partner ?? colegio.grados.length > 0) ? "Aliado" : "En Tukit",
      })),
      ...r.directorio.map((e) => ({
        clave: `dir-${e.dane}`,
        designado: { colegio_dane: e.dane, colegio_nombre: e.nombre },
        nombre: e.nombre,
        detalle: `${e.localidad} · DANE ${e.dane}`,
        logo: e.imageURL,
        marca: null,
      })),
      {
        clave: "escrito",
        designado: { colegio_nombre: consulta },
        nombre: `No lo encuentro: usar “${consulta}” tal cual`,
        detalle: "Nace como colegio nuevo al aprobar la lista",
        logo: null,
        marca: null,
        escrito: true,
      },
    ];
  }, [suficiente, preparada, consulta, imagenes]);

  const visible = abierta && opciones.length > 0;
  const indiceActivo = Math.min(activa, Math.max(opciones.length - 1, 0));

  function elegir(opcion: Opcion) {
    setElegida(opcion);
    setAbierta(false);
    onElegir(opcion.designado);
  }

  function teclear(evento: React.KeyboardEvent<HTMLInputElement>) {
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      if (!visible) {
        setAbierta(true);
        return;
      }
      const paso = evento.key === "ArrowDown" ? 1 : -1;
      setActiva((indiceActivo + paso + opciones.length) % opciones.length);
    } else if (evento.key === "Enter") {
      // Enter con la lista abierta elige; nunca envía el formulario a medias.
      if (visible) {
        evento.preventDefault();
        elegir(opciones[indiceActivo]);
      }
    } else if (evento.key === "Escape" && visible) {
      evento.preventDefault();
      setAbierta(false);
    }
  }

  if (elegida) {
    return (
      <div className={styles.campo}>
        <span>Colegio</span>
        <div className={styles.colegioElegido}>
          <span className={styles.logoColegio} aria-hidden="true">
            {elegida.escrito ? (
              <Pencil size={16} aria-hidden="true" />
            ) : (
              <LogoColegio
                src={elegida.logo}
                nombre={elegida.nombre}
                claseImagen={styles.logoImagen}
                claseIniciales={styles.logoIniciales}
              />
            )}
          </span>
          <span className={styles.opcionTexto}>
            <span className={styles.opcionNombre}>
              {elegida.escrito ? consulta : elegida.nombre}
            </span>
            <span className={styles.opcionMeta}>
              {elegida.marca ? `${elegida.marca} · ` : ""}
              {elegida.escrito ? "Escrito a mano" : elegida.detalle}
            </span>
          </span>
          <button
            type="button"
            className={styles.cambiarColegio}
            onClick={() => {
              enfocarRef.current = true;
              setElegida(null);
              setAbierta(true);
              onElegir(null);
            }}
          >
            Cambiar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.campo}>
      <span id={`${idBase}-rotulo`}>Colegio</span>
      <div className={styles.buscadorColegio}>
        <Search size={16} aria-hidden="true" className={styles.iconoBuscar} />
        <input
          ref={campoRef}
          type="text"
          role="combobox"
          aria-labelledby={`${idBase}-rotulo`}
          aria-autocomplete="list"
          aria-expanded={visible}
          aria-controls={idLista}
          aria-activedescendant={visible ? `${idLista}-${indiceActivo}` : undefined}
          value={busqueda}
          placeholder="Escribe al menos tres letras del colegio…"
          autoComplete="off"
          onFocus={() => {
            asegurarCargado();
            setAbierta(true);
          }}
          onBlur={() => setAbierta(false)}
          onChange={(e) => {
            asegurarCargado();
            setBusqueda(e.target.value);
            setActiva(0);
            setAbierta(true);
          }}
          onKeyDown={teclear}
        />
        <ul id={idLista} role="listbox" className={styles.listaColegios} hidden={!visible}>
          {opciones.map((opcion, i) => (
            <li
              key={opcion.clave}
              id={`${idLista}-${i}`}
              role="option"
              aria-selected={i === indiceActivo}
              className={`${styles.opcionColegio} ${i === indiceActivo ? styles.opcionActiva : ""} ${
                opcion.escrito ? styles.opcionEscrita : ""
              }`}
              // `mousedown` y no `click`: el `blur` del campo cerraría la lista
              // antes de que el clic llegue a la opción.
              onMouseDown={(e) => {
                e.preventDefault();
                elegir(opcion);
              }}
              onMouseEnter={() => setActiva(i)}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                {opcion.escrito ? (
                  <Pencil size={16} aria-hidden="true" />
                ) : (
                  <LogoColegio
                    src={opcion.logo}
                    nombre={opcion.nombre}
                    claseImagen={styles.logoImagen}
                    claseIniciales={styles.logoIniciales}
                  />
                )}
              </span>
              <span className={styles.opcionTexto}>
                <span className={styles.opcionNombre}>{opcion.nombre}</span>
                <span className={styles.opcionMeta}>{opcion.detalle}</span>
              </span>
              {opcion.marca ? <span className={styles.marcaColegio}>{opcion.marca}</span> : null}
            </li>
          ))}
        </ul>
      </div>
      {consulta.length > 0 && !suficiente ? (
        <span className={styles.pistaCampo}>Escribe al menos tres letras del nombre.</span>
      ) : null}
    </div>
  );
}
