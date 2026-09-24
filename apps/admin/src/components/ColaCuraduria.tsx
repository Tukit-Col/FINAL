// La cola de curaduría proactiva del catálogo (P4c bis). Lista las propuestas
// pendientes (útiles y libros que alguien encoló) y deja aprobarlas —eligiendo
// el nivel— o rechazarlas —con motivo y, opcional, `no_surtir`—.
//
// Leaf de cliente: pide `colaPropuestas()` por el Route Handler (la URL del
// backend se queda en el servidor) y refresca tras cada acción. El mensaje de
// error que muestra es el del backend tal cual, nunca uno inventado aquí.

"use client";

import { useCallback, useEffect, useState } from "react";
import { NIVELES, ETIQUETA_NIVEL } from "@tukit/contrato";
import type { Nivel, PropuestaCola } from "@tukit/contrato";
import {
  colaPropuestas,
  aprobarPropuesta,
  rechazarPropuesta,
  FalloCatalogo,
} from "@/lib/api-catalogo";
import styles from "./CatalogoSpa.module.css";

function nombreConcepto(p: PropuestaCola): string {
  if ("codigo" in p.concepto) return `${p.concepto.nombre} (${p.concepto.codigo})`;
  return p.concepto.sugerido ? `sugerido: ${p.concepto.sugerido}` : "sin concepto";
}

function precioTexto(precio: number | null): string {
  if (precio === null) return "sin precio";
  return `$${precio.toLocaleString("es-CO")}`;
}

export default function ColaCuraduria() {
  const [propuestas, setPropuestas] = useState<PropuestaCola[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // La fila que está en medio de una acción (aprobar/rechazar), por `id`.
  const [ocupada, setOcupada] = useState<string | null>(null);
  // El nivel elegido por fila para aprobar (arranca en 'confiable').
  const [niveles, setNiveles] = useState<Record<string, Nivel>>({});
  // Qué fila abrió el formulario de rechazo, con su motivo y `no_surtir`.
  const [rechazando, setRechazando] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const [noSurtir, setNoSurtir] = useState(false);

  const recargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setPropuestas(await colaPropuestas());
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos cargar la cola.");
    } finally {
      setCargando(false);
    }
  }, []);

  // La carga inicial se difiere con un `setTimeout` (mismo patrón que
  // `GestorCatalogo`) para no llamar a `setState` en el cuerpo síncrono del
  // efecto: la lectura es un `fetch`, no hay razón de bloquear el render.
  useEffect(() => {
    const t = setTimeout(() => void recargar(), 0);
    return () => clearTimeout(t);
  }, [recargar]);

  async function aprobar(p: PropuestaCola) {
    setError(null);
    setOcupada(p.id);
    try {
      await aprobarPropuesta(p.id, { nivel: niveles[p.id] ?? "confiable" });
      await recargar();
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos aprobar la propuesta.");
    } finally {
      setOcupada(null);
    }
  }

  async function rechazar(p: PropuestaCola) {
    setError(null);
    setOcupada(p.id);
    try {
      await rechazarPropuesta(p.id, {
        motivo: motivo.trim() || undefined,
        no_surtir: noSurtir || undefined,
      });
      setRechazando(null);
      setMotivo("");
      setNoSurtir(false);
      await recargar();
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos rechazar la propuesta.");
    } finally {
      setOcupada(null);
    }
  }

  return (
    <section className={styles.spa}>
      <div className={styles.tablaCabecera}>
        <span className={styles.conteo}>
          {cargando ? "Cargando…" : `${propuestas.length} propuesta(s) pendiente(s)`}
        </span>
        <button type="button" className={styles.secundario} onClick={() => void recargar()}>
          Refrescar
        </button>
      </div>

      {error && <p className={styles.error}>{error}</p>}

      {!cargando && propuestas.length === 0 && (
        <p className={styles.vacioTabla}>
          La cola está vacía. Agregá un útil o un libro y aparecerá aquí para aprobar.
        </p>
      )}

      {propuestas.map((p) => (
        <div key={p.id} className={styles.panel}>
          <header className={styles.panelCabecera}>
            <div>
              <h2>{p.nombre}</h2>
              <span className={styles.panelSku}>
                {p.id_corto} · {nombreConcepto(p)} · {precioTexto(p.precio)}
                {p.marca ? ` · ${p.marca}` : ""} · origen {p.origen}
              </span>
            </div>
          </header>

          <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
            <label className={styles.bandera}>
              Nivel
              <select
                value={niveles[p.id] ?? p.nivel_sugerido ?? "confiable"}
                onChange={(e) =>
                  setNiveles((prev) => ({ ...prev, [p.id]: e.target.value as Nivel }))
                }
              >
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
              disabled={ocupada === p.id}
              onClick={() => void aprobar(p)}
            >
              {ocupada === p.id ? "…" : "Aprobar"}
            </button>
            {rechazando === p.id ? null : (
              <button
                type="button"
                className={styles.peligro}
                disabled={ocupada === p.id}
                onClick={() => {
                  setRechazando(p.id);
                  setMotivo("");
                  setNoSurtir(false);
                }}
              >
                Rechazar
              </button>
            )}
          </div>

          {rechazando === p.id && (
            <div className={styles.confirmBaja}>
              <div className={styles.campo}>
                <label htmlFor={`motivo-${p.id}`}>Motivo (opcional)</label>
                <input
                  id={`motivo-${p.id}`}
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                  placeholder="por qué se descarta"
                />
              </div>
              <label className={styles.bandera}>
                <input
                  type="checkbox"
                  checked={noSurtir}
                  onChange={(e) => setNoSurtir(e.target.checked)}
                />
                No surtir (manda el concepto a &lsquo;no_comprar&rsquo;)
              </label>
              <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
                <button
                  type="button"
                  className={styles.peligro}
                  disabled={ocupada === p.id}
                  onClick={() => void rechazar(p)}
                >
                  {ocupada === p.id ? "…" : "Confirmar rechazo"}
                </button>
                <button
                  type="button"
                  className={styles.secundario}
                  disabled={ocupada === p.id}
                  onClick={() => setRechazando(null)}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
