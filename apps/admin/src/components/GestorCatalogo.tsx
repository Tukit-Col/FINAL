// El orquestador de cliente de la SPA de catálogo (P4c). Dueño del estado de
// filtros/paginación y de qué producto está abierto en el editor. El Server
// Component hace la PRIMERA lectura (SSR, sin filtros) y la pasa como
// `paginaInicial`; a partir de ahí toda búsqueda interactiva va por el Route
// Handler GET (`api-catalogo`), para que la URL y el token del backend se
// queden en el servidor.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  FiltrosProductos,
  Nivel,
  PaginaProductos,
  ProductoCatalogoDetalle,
} from "@tukit/contrato";
import { NIVELES, ETIQUETA_NIVEL } from "@tukit/contrato";
import { buscarProductos, FalloCatalogo } from "@/lib/api-catalogo";
import TablaProductos from "./TablaProductos";
import EditorProducto from "./EditorProducto";
import type { OpcionConcepto } from "./PanelReclasificar";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

const POR_PAGINA = 24;

// Filtros de tres estados (todos/sí/no) para las banderas booleanas.
type TriEstado = "" | "si" | "no";

function comoBandera(v: TriEstado): boolean | undefined {
  if (v === "si") return true;
  if (v === "no") return false;
  return undefined;
}

interface Props {
  paginaInicial: PaginaProductos;
  conceptos: OpcionConcepto[];
  personajes: string[];
}

export default function GestorCatalogo({ paginaInicial, conceptos, personajes }: Props) {
  const [datos, setDatos] = useState<PaginaProductos>(paginaInicial);
  const [cargando, setCargando] = useState(false);
  const [errorBusqueda, setErrorBusqueda] = useState<string | null>(null);
  const [seleccionado, setSeleccionado] = useState<ProductoCatalogoDetalle | null>(null);

  // Estado del formulario de búsqueda.
  const [busqueda, setBusqueda] = useState("");
  const [concepto, setConcepto] = useState("");
  const [nivel, setNivel] = useState<Nivel | "">("");
  const [personaje, setPersonaje] = useState("");
  const [conPersonaje, setConPersonaje] = useState<TriEstado>("");
  const [conPrecio, setConPrecio] = useState<TriEstado>("");
  const [conOfertas, setConOfertas] = useState<TriEstado>("");
  const [pagina, setPagina] = useState(paginaInicial.pagina);

  // Evita disparar la búsqueda por HTTP en el primer render: ya vino del SSR.
  const primerRender = useRef(true);

  const ejecutar = useCallback(
    async (paginaObjetivo: number) => {
      const filtros: FiltrosProductos = {
        busqueda: busqueda.trim() || undefined,
        concepto: concepto || undefined,
        nivel: nivel || undefined,
        personaje: personaje.trim() || undefined,
        con_personaje: comoBandera(conPersonaje),
        con_precio: comoBandera(conPrecio),
        con_ofertas: comoBandera(conOfertas),
        pagina: paginaObjetivo,
        por_pagina: POR_PAGINA,
      };
      setCargando(true);
      setErrorBusqueda(null);
      try {
        const resultado = await buscarProductos(filtros);
        setDatos(resultado);
        setPagina(resultado.pagina);
      } catch (causa) {
        setErrorBusqueda(
          causa instanceof FalloCatalogo ? causa.message : "No pudimos cargar el catálogo.",
        );
      } finally {
        setCargando(false);
      }
    },
    [busqueda, concepto, nivel, personaje, conPersonaje, conPrecio, conOfertas],
  );

  // Debounce: cualquier cambio de filtro re-busca desde la página 1.
  useEffect(() => {
    if (primerRender.current) {
      primerRender.current = false;
      return;
    }
    const t = setTimeout(() => void ejecutar(1), 300);
    return () => clearTimeout(t);
  }, [ejecutar]);

  function onGuardado(actualizado: ProductoCatalogoDetalle) {
    setSeleccionado(actualizado);
    setDatos((prev) => ({
      ...prev,
      productos: prev.productos.map((p) => (p.sku === actualizado.sku ? actualizado : p)),
    }));
  }

  function onEliminado(sku: string) {
    setSeleccionado(null);
    setDatos((prev) => ({
      ...prev,
      total: Math.max(0, prev.total - 1),
      productos: prev.productos.filter((p) => p.sku !== sku),
    }));
  }

  return (
    <div className={styles.spa}>
      <div className={styles.buscador}>
        <div className={styles.buscadorFila}>
          <div className={`${styles.campo} ${styles.campoBusqueda}`}>
            <label htmlFor="q">Buscar</label>
            <input
              id="q"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="nombre, marca o SKU"
            />
          </div>

          <div className={styles.campo}>
            <label htmlFor="f-concepto">Concepto</label>
            <Desplegable
              id="f-concepto"
              tamano="compacto"
              buscable
              opciones={[
                { valor: "", texto: "Todos" },
                ...conceptos.map((c) => ({ valor: c.codigo, texto: c.nombre })),
              ]}
              valor={concepto}
              onCambio={setConcepto}
            />
          </div>

          <div className={styles.campo}>
            <label htmlFor="f-nivel">Nivel</label>
            <Desplegable
              id="f-nivel"
              tamano="compacto"
              opciones={[
                { valor: "", texto: "Todos" },
                ...NIVELES.map((n) => ({ valor: n, texto: ETIQUETA_NIVEL[n] })),
              ]}
              valor={nivel}
              onCambio={(v) => setNivel(v as Nivel | "")}
            />
          </div>

          <div className={styles.campo}>
            <label htmlFor="f-personaje">Personaje</label>
            <input
              id="f-personaje"
              list="lista-personajes-filtro"
              value={personaje}
              onChange={(e) => setPersonaje(e.target.value)}
              placeholder="cualquiera"
            />
            <datalist id="lista-personajes-filtro">
              {personajes.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>
          </div>
        </div>

        <div className={styles.banderas}>
          <label className={styles.bandera}>
            Con personaje
            <Desplegable
              tamano="compacto"
              enLinea
              opciones={[
                { valor: "", texto: "todos" },
                { valor: "si", texto: "sí" },
                { valor: "no", texto: "no" },
              ]}
              valor={conPersonaje}
              onCambio={(v) => setConPersonaje(v as TriEstado)}
            />
          </label>
          <label className={styles.bandera}>
            Con precio
            <Desplegable
              tamano="compacto"
              enLinea
              opciones={[
                { valor: "", texto: "todos" },
                { valor: "si", texto: "sí" },
                { valor: "no", texto: "no" },
              ]}
              valor={conPrecio}
              onCambio={(v) => setConPrecio(v as TriEstado)}
            />
          </label>
          <label className={styles.bandera}>
            Con ofertas
            <Desplegable
              tamano="compacto"
              enLinea
              opciones={[
                { valor: "", texto: "todos" },
                { valor: "si", texto: "sí" },
                { valor: "no", texto: "no" },
              ]}
              valor={conOfertas}
              onCambio={(v) => setConOfertas(v as TriEstado)}
            />
          </label>
        </div>
      </div>

      {errorBusqueda && <p className={styles.error}>{errorBusqueda}</p>}

      <TablaProductos
        productos={datos.productos}
        total={datos.total}
        pagina={pagina}
        porPagina={datos.por_pagina || POR_PAGINA}
        cargando={cargando}
        skuActivo={seleccionado?.sku ?? null}
        onElegir={setSeleccionado}
        onPagina={(p) => void ejecutar(p)}
      />

      {seleccionado && (
        <EditorProducto
          key={seleccionado.sku}
          producto={seleccionado}
          conceptos={conceptos}
          personajes={personajes}
          onGuardado={onGuardado}
          onEliminado={onEliminado}
          onCerrar={() => setSeleccionado(null)}
        />
      )}
    </div>
  );
}
