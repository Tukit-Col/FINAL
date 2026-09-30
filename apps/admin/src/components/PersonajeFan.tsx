"use client";

// El interruptor de personaje del kit Fan (rediseño §7, 2d).
//
// El Fan es el kit "con licencia": sus cuatro anclas —cuaderno, cartuchera,
// carpeta, maleta— llevan el personaje que el niño pidió. El optimizador NO las
// elige de una franquicia (deprioriza los productos con personaje, consulta.py),
// así que aplicar un personaje es una BÚSQUEDA determinista, no un re-ranking:
// se piden los 4 anclas de esa franquicia al catálogo y se fija cada uno en su
// línea del kit Fan con la ruta por-nivel (`fijarProductoLinea`), la misma que
// usa el swap. Sin NSGA, sin tocar los otros dos kits.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import type { Kit, ProductoCatalogoDetalle } from "@tukit/contrato";
import { formatearPesos } from "@tukit/contrato";
import { buscarProductos, FalloCatalogo } from "@/lib/api-catalogo";
import { FalloApi, fijarProductoLinea } from "@/lib/api-navegador";
import styles from "./Revision.module.css";

// Los conceptos ancla, espejo de `CONCEPTOS_ANCLA` en optimizador.py:91
// (cuaderno / cartuchera / carpeta / maleta). Es el único acoplamiento: si allá
// cambian, cambia aquí. No hay un contrato que los exponga y no vale inventarlo
// para cuatro códigos estables.
const CONCEPTOS_ANCLA = ["C001", "C009", "C011", "C086"] as const;

interface Props {
  trabajoId: string;
  // El kit Fan. Sus líneas dan qué anclas existen de verdad en este trabajo
  // (una lista puede no pedir maleta) y el item_id sobre el que escribir.
  fan: Kit;
  personajes: string[];
}

interface Ancla {
  itemId: string;
  concepto: string;
  descripcion: string;
  skuActual: string | null;
}

export default function PersonajeFan({ trabajoId, fan, personajes }: Props) {
  const router = useRouter();
  const [elegido, setElegido] = useState<string>("");
  const [previos, setPrevios] = useState<Map<string, ProductoCatalogoDetalle>>(new Map());
  const [cargando, setCargando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  // Las anclas que este kit Fan sí tiene, en el orden canónico.
  const anclas: Ancla[] = CONCEPTOS_ANCLA.flatMap((concepto) => {
    const linea = fan.lineas.find((l) => l.concepto === concepto);
    return linea
      ? [
          {
            itemId: linea.item_id,
            concepto,
            descripcion: linea.descripcion,
            skuActual: linea.producto_elegido?.sku ?? null,
          },
        ]
      : [];
  });

  if (anclas.length === 0) return null;

  async function previsualizar(personaje: string): Promise<void> {
    setElegido(personaje);
    setPrevios(new Map());
    setError(null);
    setAviso(null);
    if (!personaje) return;
    setCargando(true);
    try {
      // Una llamada por ancla: el catálogo filtra por concepto+personaje y
      // devuelve el/los producto(s) de esa franquicia para ese concepto. Se
      // toma el primero (el mejor por quality_score, como los ordena el
      // catálogo). ponytail: 4 llamadas; un endpoint de conveniencia solo si
      // el chatter molesta de verdad.
      const encontrados = new Map<string, ProductoCatalogoDetalle>();
      await Promise.all(
        anclas.map(async (ancla) => {
          const pagina = await buscarProductos({
            concepto: ancla.concepto,
            personaje,
            por_pagina: 1,
          });
          const primero = pagina.productos[0];
          if (primero) encontrados.set(ancla.concepto, primero);
        }),
      );
      setPrevios(encontrados);
      if (encontrados.size === 0) {
        setError(`No hay productos de ${personaje} para ninguna de las anclas.`);
      }
    } catch (causa) {
      setError(
        causa instanceof FalloCatalogo ? causa.message : "No pudimos buscar la franquicia.",
      );
    } finally {
      setCargando(false);
    }
  }

  async function aplicar(): Promise<void> {
    setError(null);
    setAviso(null);
    setAplicando(true);
    let hechas = 0;
    try {
      // En secuencia: cada `fijarProductoLinea` recalcula el total del kit Fan,
      // y una ráfaga simultánea pelearía por ese recálculo (igual que el lote
      // de validación). Solo las anclas para las que hubo producto.
      for (const ancla of anclas) {
        const producto = previos.get(ancla.concepto);
        if (!producto) continue;
        await fijarProductoLinea(trabajoId, "Fan", ancla.itemId, producto.sku);
        hechas += 1;
      }
      setAviso(`${hechas} ancla(s) del Fan cambiadas a ${elegido}.`);
      router.refresh();
    } catch (causa) {
      setError(
        `Se aplicaron ${hechas}. ${
          causa instanceof FalloApi ? causa.message : "No pudimos aplicar el resto."
        }`,
      );
      router.refresh();
    } finally {
      setAplicando(false);
    }
  }

  return (
    <section className={styles.personajeFan}>
      <div className={styles.personajeFanCabecera}>
        <Sparkles size={15} strokeWidth={2.4} aria-hidden="true" />
        <h3>Personaje del kit Fan</h3>
        <p>
          Cambia las {anclas.length} anclas —{anclas.map((a) => a.descripcion).join(", ")}— a una
          franquicia. Solo toca el kit Fan.
        </p>
      </div>

      <div className={styles.personajeFanControl}>
        <select
          aria-label="Franquicia del kit Fan"
          value={elegido}
          disabled={cargando || aplicando}
          onChange={(evento) => void previsualizar(evento.target.value)}
        >
          <option value="">Elegir personaje…</option>
          {personajes.map((personaje) => (
            <option key={personaje} value={personaje}>
              {personaje}
            </option>
          ))}
        </select>
        {cargando ? <span className={styles.personajeFanEstado}>Buscando…</span> : null}
      </div>

      {previos.size > 0 ? (
        <>
          <ul className={styles.personajeFanPreview}>
            {anclas.map((ancla) => {
              const producto = previos.get(ancla.concepto);
              return (
                <li key={ancla.itemId} className={styles.personajeFanItem}>
                  <span className={styles.personajeFanConcepto}>{ancla.descripcion}</span>
                  {producto ? (
                    <>
                      {producto.imagen_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={producto.imagen_url} alt="" className={styles.celdaMini} />
                      ) : (
                        <span className={styles.celdaMiniVacia} aria-hidden="true" />
                      )}
                      <span className={styles.personajeFanNombre}>{producto.nombre}</span>
                      <span className={`${styles.celdaPrecio} cifra`}>
                        {formatearPesos(producto.precio_desde)}
                      </span>
                    </>
                  ) : (
                    <span className={styles.celdaSinProducto}>
                      Sin {elegido} para esta ancla — se deja como está
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          <button
            type="button"
            className={styles.principal}
            disabled={aplicando}
            onClick={() => void aplicar()}
          >
            {aplicando ? "Aplicando…" : `Aplicar ${elegido} al kit Fan`}
          </button>
        </>
      ) : null}

      {error ? <p className={styles.error}>{error}</p> : null}
      {aviso ? <p className={styles.exito}>{aviso}</p> : null}
    </section>
  );
}
