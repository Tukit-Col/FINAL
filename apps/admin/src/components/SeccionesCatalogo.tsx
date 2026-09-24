// El caparazón de pestañas de /catalogo (P4c bis). Cambia entre las cuatro
// vistas: el gestor de productos (búsqueda + editor, lo que ya existía), la
// cola de curaduría, y las dos altas (útil por búsqueda en tienda, libro
// manual). Cliente porque el cambio de pestaña es interactivo; cada vista es su
// propio leaf y habla con los Route Handlers.
//
// La cola tiene una `key` que se bumpea al encolar, para forzar su recarga
// cuando una alta mete algo nuevo (y así se ve reflejado sin refrescar a mano).

"use client";

import { useState } from "react";
import type { PaginaProductos } from "@tukit/contrato";
import GestorCatalogo from "./GestorCatalogo";
import ColaCuraduria from "./ColaCuraduria";
import AltaUtil from "./AltaUtil";
import AltaLibro from "./AltaLibro";
import type { OpcionConcepto } from "./PanelReclasificar";
import styles from "./CatalogoSpa.module.css";

type Pestana = "productos" | "cola" | "util" | "libro";

const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: "productos", nombre: "Productos" },
  { id: "cola", nombre: "Cola de curaduría" },
  { id: "util", nombre: "Agregar útil" },
  { id: "libro", nombre: "Agregar libro" },
];

interface Props {
  paginaInicial: PaginaProductos;
  conceptos: OpcionConcepto[];
  personajes: string[];
}

export default function SeccionesCatalogo({ paginaInicial, conceptos, personajes }: Props) {
  const [pestana, setPestana] = useState<Pestana>("productos");
  // Se incrementa al encolar algo; `ColaCuraduria` se remonta y recarga.
  const [versionCola, setVersionCola] = useState(0);

  function irALaCola() {
    setVersionCola((v) => v + 1);
    setPestana("cola");
  }

  return (
    <div>
      <nav className={styles.pestanas} aria-label="Vistas del catálogo">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`${styles.pestana} ${pestana === p.id ? styles.pestanaActiva : ""}`}
            aria-current={pestana === p.id}
            onClick={() => setPestana(p.id)}
          >
            {p.nombre}
          </button>
        ))}
      </nav>

      {pestana === "productos" && (
        <GestorCatalogo
          paginaInicial={paginaInicial}
          conceptos={conceptos}
          personajes={personajes}
        />
      )}
      {pestana === "cola" && <ColaCuraduria key={versionCola} />}
      {pestana === "util" && <AltaUtil conceptos={conceptos} onEncolado={irALaCola} />}
      {pestana === "libro" && <AltaLibro conceptos={conceptos} onEncolado={irALaCola} />}
    </div>
  );
}
