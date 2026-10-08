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
import type { ConceptoCreado, PaginaProductos } from "@tukit/contrato";
import GestorCatalogo from "./GestorCatalogo";
import ColaCuraduria from "./ColaCuraduria";
import AltaUtil from "./AltaUtil";
import AltaLibro from "./AltaLibro";
import NuevoConcepto from "./NuevoConcepto";
import type { OpcionConcepto } from "./PanelReclasificar";
import type { VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import styles from "./CatalogoSpa.module.css";

// Una tienda registrada para los selectores de alta (se puede elegir una o
// escribir otro slug; el backend valida contra la BD).
export interface OpcionTienda {
  slug: string;
  nombre: string;
}

type Pestana = "productos" | "cola" | "concepto" | "util" | "libro";

const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: "productos", nombre: "Productos" },
  { id: "cola", nombre: "Cola de curaduría" },
  { id: "concepto", nombre: "Nuevo concepto" },
  { id: "util", nombre: "Agregar útil" },
  { id: "libro", nombre: "Agregar libro" },
];

interface Props {
  paginaInicial: PaginaProductos;
  conceptos: OpcionConcepto[];
  personajes: string[];
  tiendas: OpcionTienda[];
  vocabulario: VocabularioConceptos;
  /** La pestaña con que abre (`?pestana=util`); por omisión, productos. */
  pestanaInicial?: string;
  /** Lo que el alta de útil trae ya puesto (desde un aviso de una lista). */
  altaInicial?: { concepto?: string; consulta?: string };
}

export default function SeccionesCatalogo({
  paginaInicial,
  conceptos: conceptosIniciales,
  personajes,
  tiendas,
  vocabulario,
  pestanaInicial,
  altaInicial,
}: Props) {
  const [pestana, setPestana] = useState<Pestana>(
    PESTANAS.some((p) => p.id === pestanaInicial) ? (pestanaInicial as Pestana) : "productos",
  );
  // Se incrementa al encolar algo; `ColaCuraduria` se remonta y recarga.
  const [versionCola, setVersionCola] = useState(0);
  // Los conceptos viven en estado para que uno recién creado aparezca de
  // inmediato en los selectores de las altas, sin refrescar la página.
  const [conceptos, setConceptos] = useState<OpcionConcepto[]>(conceptosIniciales);

  function irALaCola() {
    setVersionCola((v) => v + 1);
    setPestana("cola");
  }

  function alCrearConcepto(creado: ConceptoCreado) {
    setConceptos((previos) => [
      ...previos,
      {
        codigo: creado.codigo,
        nombre: creado.nombre_canonico,
        atributos_discriminantes: creado.atributos_discriminantes,
        atributos_descriptivos: creado.atributos_descriptivos,
      },
    ]);
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
      {pestana === "cola" && (
        <ColaCuraduria key={versionCola} conceptos={conceptos} personajes={personajes} />
      )}
      {pestana === "concepto" && (
        <NuevoConcepto
          onCreado={alCrearConcepto}
          atributosConocidos={vocabulario.atributos}
          categoriasConocidas={vocabulario.categorias}
        />
      )}
      {pestana === "util" && (
        <AltaUtil
          conceptos={conceptos}
          tiendas={tiendas}
          onEncolado={irALaCola}
          conceptoInicial={altaInicial?.concepto}
          consultaInicial={altaInicial?.consulta}
        />
      )}
      {pestana === "libro" && (
        <AltaLibro conceptos={conceptos} tiendas={tiendas} onEncolado={irALaCola} />
      )}
    </div>
  );
}
