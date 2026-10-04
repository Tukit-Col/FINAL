"use client";

// Menú de concepto con buscador que SIEMPRE abre hacia abajo.
//
// Con un <select> nativo de ~150 conceptos el navegador decide hacia dónde se
// despliega, y en el editor de un renglón (casi siempre en la mitad baja de la
// pantalla) lo abría hacia arriba, tapando el renglón que se estaba editando.
// Un select nativo no deja elegir la dirección, así que este panel se pinta
// debajo del campo, con un buscador por nombre o código.

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { OpcionConcepto } from "./PanelReclasificar";
import styles from "./SelectorConcepto.module.css";

interface Props {
  conceptos: OpcionConcepto[];
  valor: string;
  onCambio: (codigo: string) => void;
  disabled?: boolean;
  /** Texto de la opción vacía (valor ""). */
  textoVacio?: string;
  /** id para el `htmlFor` del rótulo. */
  id?: string;
}

function sinTildes(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export default function SelectorConcepto({
  conceptos,
  valor,
  onCambio,
  disabled = false,
  textoVacio = "— sin concepto —",
  id,
}: Props) {
  const idLista = useId();
  const [abierto, setAbierto] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [activo, setActivo] = useState(0);
  const caja = useRef<HTMLDivElement>(null);
  const lista = useRef<HTMLUListElement>(null);

  // La opción vacía va primero y sale siempre, salvo que se esté buscando.
  const opciones = useMemo(() => {
    const q = sinTildes(busqueda.trim());
    const filtradas = q
      ? conceptos.filter((c) => sinTildes(`${c.nombre} ${c.codigo}`).includes(q))
      : conceptos;
    const todas = filtradas.map((c) => ({ codigo: c.codigo, texto: `${c.nombre} (${c.codigo})` }));
    return q ? todas : [{ codigo: "", texto: textoVacio }, ...todas];
  }, [conceptos, busqueda, textoVacio]);

  const elegido = conceptos.find((c) => c.codigo === valor);
  const etiqueta = elegido ? `${elegido.nombre} (${elegido.codigo})` : textoVacio;

  // Cerrar al hacer clic fuera.
  useEffect(() => {
    if (!abierto) return;
    function fuera(evento: MouseEvent) {
      if (caja.current && !caja.current.contains(evento.target as Node)) setAbierto(false);
    }
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  // Mantener visible la opción activa al moverse con el teclado.
  useEffect(() => {
    lista.current?.children[activo]?.scrollIntoView({ block: "nearest" });
  }, [activo]);

  function abrir() {
    if (disabled) return;
    setBusqueda("");
    const indice = conceptos.findIndex((c) => c.codigo === valor);
    setActivo(indice >= 0 ? indice + 1 : 0);
    setAbierto(true);
  }

  function elegir(codigo: string) {
    onCambio(codigo);
    setAbierto(false);
  }

  function teclas(evento: React.KeyboardEvent) {
    if (evento.key === "ArrowDown") {
      evento.preventDefault();
      setActivo((i) => Math.min(i + 1, opciones.length - 1));
    } else if (evento.key === "ArrowUp") {
      evento.preventDefault();
      setActivo((i) => Math.max(i - 1, 0));
    } else if (evento.key === "Enter") {
      evento.preventDefault();
      const opcion = opciones[activo];
      if (opcion) elegir(opcion.codigo);
    } else if (evento.key === "Escape") {
      evento.preventDefault();
      setAbierto(false);
    }
  }

  return (
    <div className={styles.caja} ref={caja}>
      <button
        id={id}
        type="button"
        className={styles.campo}
        onClick={() => (abierto ? setAbierto(false) : abrir())}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={abierto}
      >
        <span className={styles.etiqueta}>{etiqueta}</span>
        <span className={styles.flecha} aria-hidden="true">
          ▾
        </span>
      </button>

      {abierto ? (
        <div className={styles.panel}>
          <input
            className={styles.buscador}
            value={busqueda}
            autoFocus
            placeholder="Buscar por nombre o código…"
            onChange={(e) => {
              setBusqueda(e.target.value);
              setActivo(0);
            }}
            onKeyDown={teclas}
            role="combobox"
            aria-controls={idLista}
            aria-expanded="true"
          />
          <ul id={idLista} ref={lista} className={styles.lista} role="listbox">
            {opciones.length === 0 ? (
              <li className={styles.vacio}>Ningún concepto coincide.</li>
            ) : (
              opciones.map((opcion, indice) => (
                <li
                  key={opcion.codigo || "vacio"}
                  role="option"
                  aria-selected={opcion.codigo === valor}
                  className={`${styles.opcion} ${indice === activo ? styles.activa : ""} ${
                    opcion.codigo === valor ? styles.elegida : ""
                  }`}
                  onMouseEnter={() => setActivo(indice)}
                  onMouseDown={(e) => {
                    // mousedown y no click: que el buscador no pierda el foco
                    // antes de elegir.
                    e.preventDefault();
                    elegir(opcion.codigo);
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
