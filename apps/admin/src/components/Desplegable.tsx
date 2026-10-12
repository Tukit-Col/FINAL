"use client";

// Menú desplegable que SIEMPRE abre hacia abajo, con buscador opcional.
//
// Un <select> nativo lo despliega el navegador hacia donde quiera, y en los
// formularios del admin (casi siempre en la mitad baja de la pantalla) lo abría
// hacia arriba, tapando el formulario. No hay CSS que cambie eso, así que este
// panel se pinta debajo del campo. Es el mismo menú para concepto, tipo y
// atributos, para que todos se vean y se manejen igual.

import { useEffect, useId, useMemo, useRef, useState } from "react";
import styles from "./Desplegable.module.css";

export interface OpcionDesplegable {
  valor: string;
  texto: string;
  /** Se ve pero no se puede elegir (p. ej. el concepto actual al reclasificar). */
  deshabilitada?: boolean;
}

interface Props {
  opciones: OpcionDesplegable[];
  valor: string;
  onCambio: (valor: string) => void;
  disabled?: boolean;
  /** Lo que se ve cuando `valor` no es ninguna opción (p. ej. "Elegir…"). */
  textoVacio?: string;
  /** Con muchas opciones: un buscador arriba del panel (sin tildes). */
  buscable?: boolean;
  /** "compacto" para los formularios densos del catálogo. */
  tamano?: "normal" | "compacto";
  /** Junto a un texto en la misma línea (filtros): ancho de su contenido. */
  enLinea?: boolean;
  /** id para el `htmlFor` del rótulo. */
  id?: string;
}

function sinTildes(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export default function Desplegable({
  opciones,
  valor,
  onCambio,
  disabled = false,
  textoVacio = "Elegir…",
  buscable = false,
  tamano = "normal",
  enLinea = false,
  id,
}: Props) {
  const idLista = useId();
  const [abierto, setAbierto] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [activo, setActivo] = useState(0);
  const caja = useRef<HTMLDivElement>(null);
  const lista = useRef<HTMLUListElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);

  const visibles = useMemo(() => {
    const q = sinTildes(busqueda.trim());
    return q ? opciones.filter((o) => sinTildes(`${o.texto} ${o.valor}`).includes(q)) : opciones;
  }, [opciones, busqueda]);

  const elegida = opciones.find((o) => o.valor === valor);

  // Cerrar al hacer clic fuera.
  useEffect(() => {
    if (!abierto) return;
    function fuera(evento: MouseEvent) {
      if (caja.current && !caja.current.contains(evento.target as Node)) setAbierto(false);
    }
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  // Si el campo vive en una caja con scroll propio (la lista de renglones del
  // revisor), que esa caja baje lo justo para mostrar el panel completo.
  useEffect(() => {
    if (abierto) panel.current?.scrollIntoView({ block: "nearest" });
  }, [abierto]);

  // Mantener visible la opción activa al moverse con el teclado.
  useEffect(() => {
    if (abierto) lista.current?.children[activo]?.scrollIntoView({ block: "nearest" });
  }, [activo, abierto]);

  function abrir() {
    if (disabled) return;
    setBusqueda("");
    const indice = opciones.findIndex((o) => o.valor === valor);
    setActivo(Math.max(indice, 0));
    setAbierto(true);
  }

  function cerrar() {
    setAbierto(false);
    boton.current?.focus();
  }

  function elegir(opcion: OpcionDesplegable) {
    if (opcion.deshabilitada) return;
    onCambio(opcion.valor);
    cerrar();
  }

  function teclas(evento: React.KeyboardEvent) {
    if (evento.key === "ArrowDown") {
      evento.preventDefault();
      if (!abierto) abrir();
      else setActivo((i) => Math.min(i + 1, visibles.length - 1));
    } else if (evento.key === "ArrowUp") {
      evento.preventDefault();
      setActivo((i) => Math.max(i - 1, 0));
    } else if (evento.key === "Enter" && abierto) {
      evento.preventDefault();
      const opcion = visibles[activo];
      if (opcion) elegir(opcion);
    } else if (evento.key === "Escape" && abierto) {
      evento.preventDefault();
      cerrar();
    }
  }

  return (
    <div className={`${styles.caja} ${enLinea ? styles.enLinea : ""}`} ref={caja}>
      <button
        id={id}
        ref={boton}
        type="button"
        className={`${styles.campo} ${tamano === "compacto" ? styles.compacto : ""}`}
        onClick={() => (abierto ? setAbierto(false) : abrir())}
        onKeyDown={buscable ? undefined : teclas}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={abierto}
        aria-controls={abierto ? idLista : undefined}
      >
        <span className={`${styles.etiqueta} ${elegida ? "" : styles.etiquetaVacia}`}>
          {elegida ? elegida.texto : textoVacio}
        </span>
        <span className={styles.flecha} aria-hidden="true">
          ▾
        </span>
      </button>

      {abierto ? (
        <div className={styles.panel} ref={panel}>
          {buscable ? (
            <input
              className={styles.buscador}
              value={busqueda}
              autoFocus
              placeholder="Buscar…"
              onChange={(e) => {
                setBusqueda(e.target.value);
                setActivo(0);
              }}
              onKeyDown={teclas}
              role="combobox"
              aria-controls={idLista}
              aria-expanded="true"
            />
          ) : null}
          <ul id={idLista} ref={lista} className={styles.lista} role="listbox">
            {visibles.length === 0 ? (
              <li className={styles.vacio}>Nada coincide.</li>
            ) : (
              visibles.map((opcion, indice) => (
                <li
                  key={opcion.valor || "vacio"}
                  role="option"
                  aria-selected={opcion.valor === valor}
                  aria-disabled={opcion.deshabilitada || undefined}
                  className={`${styles.opcion} ${indice === activo ? styles.activa : ""} ${
                    opcion.valor === valor ? styles.elegida : ""
                  } ${opcion.deshabilitada ? styles.deshabilitada : ""}`}
                  onMouseEnter={() => setActivo(indice)}
                  onMouseDown={(e) => {
                    // mousedown y no click: que el buscador no pierda el foco
                    // antes de elegir.
                    e.preventDefault();
                    elegir(opcion);
                  }}
                >
                  {opcion.texto}
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
