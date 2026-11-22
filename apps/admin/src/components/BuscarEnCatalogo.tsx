"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import type { ProductoCatalogoDetalle } from "@tukit/contrato";
import { formatearPesos } from "@tukit/contrato";
import { buscarProductos } from "@/lib/api-catalogo";
import styles from "./Revision.module.css";

const PALABRAS_VACIAS = new Set(["de", "del", "la", "el", "los", "las", "para", "con", "y", "x", "un", "una"]);

function consultaDe(texto: string): string {
  return texto
    .toLowerCase()
    .replace(/[^\p{L}\p{N} ]/gu, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !PALABRAS_VACIAS.has(w) && !/^\d+$/.test(w))
    .slice(0, 3)
    .join(" ");
}

export default function BuscarEnCatalogo({
  concepto,
  textoInicial,
  enviando,
  onElegir,
}: {
  concepto: string | null;
  textoInicial: string;
  enviando: boolean;
  onElegir: (sku: string) => void;
}) {
  const [texto, setTexto] = useState(() => consultaDe(textoInicial));
  const [soloConcepto, setSoloConcepto] = useState(Boolean(concepto));
  const [productos, setProductos] = useState<ProductoCatalogoDetalle[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    const espera = setTimeout(() => {
      buscarProductos({
        busqueda: texto,
        ...(soloConcepto && concepto ? { concepto } : {}),
        con_precio: true,
        por_pagina: 12,
      })
        .then((r) => vivo && (setProductos(r.productos), setError(null)))
        .catch(() => vivo && setError("No pudimos buscar en el catálogo."));
    }, 250);
    return () => {
      vivo = false;
      clearTimeout(espera);
    };
  }, [texto, soloConcepto, concepto]);

  return (
    <div className={styles.buscarCatalogo}>
      <div className={styles.buscarFila}>
        <label className={styles.buscarCampo}>
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Buscar en el catálogo"
            aria-label="Buscar un producto del catálogo"
          />
        </label>
        {concepto ? (
          <label className={styles.buscarFiltro}>
            <input type="checkbox" checked={soloConcepto} onChange={(e) => setSoloConcepto(e.target.checked)} />
            Solo {concepto}
          </label>
        ) : null}
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
      {productos === null ? null : productos.length === 0 ? (
        <p className={styles.detalle}>No encontramos productos con eso. Prueba con otra palabra o quita el filtro.</p>
      ) : (
        <ul className={styles.buscarResultados}>
          {productos.map((p) => (
            <li key={p.sku}>
              {p.imagen_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.imagen_url} alt="" loading="lazy" />
              ) : (
                <span aria-hidden="true" />
              )}
              <span className={styles.buscarNombre}>
                {p.nombre}
                <small>
                  {[p.marca, p.concepto?.nombre].filter(Boolean).join(" · ")}
                </small>
              </span>
              <span className="cifra">{p.precio_desde != null ? formatearPesos(p.precio_desde) : "—"}</span>
              <button type="button" disabled={enviando} onClick={() => onElegir(p.sku)}>
                Usar este
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
