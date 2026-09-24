// Alta de un útil por búsqueda en vivo en la tienda (P4c bis). Selector de
// tienda + caja de búsqueda → candidatos (foto, nombre, precio, marca) → se
// elige uno + concepto + nivel → `altaUtil` lo ENCOLA (no lo aprueba: cae en la
// cola visible). El backend re-busca por `(slug, sku)` para no confiar en un
// precio que el navegador pudo alterar.
//
// Leaf de cliente: habla con los Route Handlers de esta app; la URL del backend
// se queda en el servidor. El mensaje de error es el del backend tal cual.

"use client";

import { useState } from "react";
import { NIVELES, ETIQUETA_NIVEL } from "@tukit/contrato";
import type { CandidatoTienda, Nivel } from "@tukit/contrato";
import { buscarEnTienda, altaUtil, FalloCatalogo } from "@/lib/api-catalogo";
import type { OpcionConcepto } from "./PanelReclasificar";
import styles from "./CatalogoSpa.module.css";

// Los slugs que el backend acepta (`tiendas.buscar`): Éxito y Panamericana por
// VTEX, Gran Central por Shopify.
const TIENDAS: { slug: string; nombre: string }[] = [
  { slug: "exito", nombre: "Éxito" },
  { slug: "panamericana", nombre: "Panamericana" },
  { slug: "grancentral", nombre: "Gran Central" },
];

interface Props {
  conceptos: OpcionConcepto[];
  onEncolado: () => void;
}

export default function AltaUtil({ conceptos, onEncolado }: Props) {
  const [slug, setSlug] = useState(TIENDAS[0]!.slug);
  const [consulta, setConsulta] = useState("");
  const [candidatos, setCandidatos] = useState<CandidatoTienda[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  // El candidato elegido, con concepto y nivel para encolar.
  const [elegido, setElegido] = useState<CandidatoTienda | null>(null);
  const [concepto, setConcepto] = useState("");
  const [nivel, setNivel] = useState<Nivel>("confiable");
  const [encolando, setEncolando] = useState(false);

  async function buscar() {
    if (!consulta.trim()) return;
    setError(null);
    setExito(null);
    setElegido(null);
    setBuscando(true);
    try {
      setCandidatos(await buscarEnTienda(slug, consulta.trim()));
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos buscar en la tienda.");
    } finally {
      setBuscando(false);
    }
  }

  async function encolar() {
    if (!elegido || !concepto) return;
    setError(null);
    setExito(null);
    setEncolando(true);
    try {
      const r = await altaUtil({ concepto, slug: elegido.slug, sku: elegido.sku, consulta, nivel });
      setExito(`Encolado (${r.id_corto}). Revisalo en la cola para aprobarlo.`);
      setElegido(null);
      onEncolado();
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos encolar el útil.");
    } finally {
      setEncolando(false);
    }
  }

  return (
    <section className={styles.spa}>
      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      <div className={styles.buscadorFila}>
        <div className={styles.campo}>
          <label htmlFor="au-tienda">Tienda</label>
          <select id="au-tienda" value={slug} onChange={(e) => setSlug(e.target.value)}>
            {TIENDAS.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.nombre}
              </option>
            ))}
          </select>
        </div>
        <div className={`${styles.campo} ${styles.campoBusqueda}`}>
          <label htmlFor="au-consulta">Buscar</label>
          <input
            id="au-consulta"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void buscar();
            }}
            placeholder="cuaderno, lápiz, témpera…"
          />
        </div>
        <button
          type="button"
          className={styles.secundario}
          disabled={buscando || !consulta.trim()}
          onClick={() => void buscar()}
          style={{ alignSelf: "flex-end" }}
        >
          {buscando ? "Buscando…" : "Buscar"}
        </button>
      </div>

      {candidatos.length === 0 && !buscando && (
        <p className={styles.vacioTabla}>
          Buscá un útil en la tienda para ver candidatos y encolar uno.
        </p>
      )}

      {candidatos.map((c) => (
        <div
          key={`${c.slug}:${c.sku}`}
          className={`${styles.panel} ${elegido?.sku === c.sku ? styles.filaActiva : ""}`}
        >
          <header className={styles.panelCabecera}>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              {c.imagen_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img className={styles.miniatura} src={c.imagen_url} alt="" />
              ) : (
                <span className={styles.miniaturaVacia}>—</span>
              )}
              <div>
                <h2>{c.nombre}</h2>
                <span className={styles.panelSku}>
                  {c.sku} · ${c.precio.toLocaleString("es-CO")}
                  {c.marca ? ` · ${c.marca}` : ""}
                  {c.disponible ? "" : " · agotado"}
                </span>
              </div>
            </div>
            <button
              type="button"
              className={styles.secundario}
              onClick={() => {
                setElegido(c);
                setExito(null);
              }}
            >
              {elegido?.sku === c.sku ? "Elegido" : "Elegir"}
            </button>
          </header>

          {elegido?.sku === c.sku && (
            <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
              <div className={styles.campo}>
                <label htmlFor="au-concepto">Concepto</label>
                <select
                  id="au-concepto"
                  value={concepto}
                  onChange={(e) => setConcepto(e.target.value)}
                >
                  <option value="">— elegir concepto —</option>
                  {conceptos.map((op) => (
                    <option key={op.codigo} value={op.codigo}>
                      {op.nombre}
                    </option>
                  ))}
                </select>
              </div>
              <label className={styles.bandera}>
                Nivel sugerido
                <select value={nivel} onChange={(e) => setNivel(e.target.value as Nivel)}>
                  {NIVELES.map((n) => (
                    <option key={n} value={n}>
                      {ETIQUETA_NIVEL[n]}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className={styles.principal}
                disabled={!concepto || encolando}
                onClick={() => void encolar()}
              >
                {encolando ? "Encolando…" : "Encolar a la cola"}
              </button>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
