"use client";

import { useMemo, useState } from "react";
import { NIVELES, ETIQUETA_NIVEL } from "@tukit/contrato";
import type { Nivel } from "@tukit/contrato";
import { altaLibro, FalloCatalogo } from "@/lib/api-catalogo";
import type { OpcionConcepto } from "./PanelReclasificar";
import type { OpcionTienda } from "./SeccionesCatalogo";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

interface Props {
  conceptos: OpcionConcepto[];
  tiendas: OpcionTienda[];
  onEncolado: () => void;
}

export default function AltaLibro({ conceptos, tiendas, onEncolado }: Props) {
  const [isbn, setIsbn] = useState("");
  const [titulo, setTitulo] = useState("");
  const [precio, setPrecio] = useState("");
  const [slug, setSlug] = useState(tiendas[0]?.slug ?? "panamericana");
  const [concepto, setConcepto] = useState("");
  const [nivel, setNivel] = useState<Nivel>("confiable");

  const [encolando, setEncolando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const precioNum = Number(precio);
  const precioValido = Number.isInteger(precioNum) && precioNum > 0;

  const enlaceBuscalibre = useMemo(() => {
    const q = (isbn.trim() || titulo.trim()) ?? "";
    return `https://www.buscalibre.com.co/libros/search?q=${encodeURIComponent(q)}`;
  }, [isbn, titulo]);

  const puedeEncolar =
    isbn.trim().length > 0 &&
    titulo.trim().length > 0 &&
    precioValido &&
    concepto.length > 0 &&
    slug.trim().length > 0;

  async function encolar() {
    setError(null);
    setExito(null);
    if (!puedeEncolar) {
      setError("Revisá ISBN, título, precio (entero en pesos > 0) y concepto.");
      return;
    }
    setEncolando(true);
    try {
      const r = await altaLibro({
        concepto,
        isbn: isbn.trim(),
        titulo: titulo.trim(),
        precio: precioNum,
        slug: slug.trim(),
        nivel,
      });
      setExito(`Encolado (${r.id_corto}). Revisalo en la cola para aprobarlo.`);
      setIsbn("");
      setTitulo("");
      setPrecio("");
      onEncolado();
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos encolar el libro.");
    } finally {
      setEncolando(false);
    }
  }

  return (
    <section className={styles.spa}>
      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      <p className={styles.nota}>
        Buscalibre no tiene búsqueda en vivo. Abrí el link, copiá ISBN, título y precio, y pegalos
        aquí.{" "}
        <a href={enlaceBuscalibre} target="_blank" rel="noopener">
          Buscar en Buscalibre
        </a>
      </p>

      <div className={styles.rejilla}>
        <div className={styles.campo}>
          <label htmlFor="al-isbn">ISBN</label>
          <input
            id="al-isbn"
            value={isbn}
            onChange={(e) => setIsbn(e.target.value)}
            placeholder="978…"
          />
        </div>

        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor="al-titulo">Título</label>
          <input id="al-titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </div>

        <div className={styles.campo}>
          <label htmlFor="al-precio">Precio (pesos)</label>
          <input
            id="al-precio"
            type="number"
            min={1}
            step={1}
            value={precio}
            onChange={(e) => setPrecio(e.target.value)}
          />
          {precio.trim() !== "" && !precioValido && (
            <span className={`${styles.ayuda} ${styles.ayudaError}`}>
              Un entero en pesos mayor que 0.
            </span>
          )}
        </div>

        <div className={styles.campo}>
          <label htmlFor="al-tienda">Tienda</label>
          <input
            id="al-tienda"
            list="al-tiendas"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="elegí o escribí un slug"
          />
          <datalist id="al-tiendas">
            {tiendas.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.nombre}
              </option>
            ))}
          </datalist>
        </div>

        <div className={styles.campo}>
          <label htmlFor="al-concepto">Concepto</label>
          <Desplegable
            id="al-concepto"
            tamano="compacto"
            buscable
            textoVacio="— elegir concepto —"
            opciones={conceptos.map((op) => ({ valor: op.codigo, texto: op.nombre }))}
            valor={concepto}
            onCambio={setConcepto}
          />
        </div>

        <div className={styles.campo}>
          <label htmlFor="al-nivel">Nivel sugerido</label>
          <Desplegable
            id="al-nivel"
            tamano="compacto"
            opciones={NIVELES.map((n) => ({ valor: n, texto: ETIQUETA_NIVEL[n] }))}
            valor={nivel}
            onCambio={(v) => setNivel(v as Nivel)}
          />
        </div>
      </div>

      <div className={styles.acciones}>
        <button
          type="button"
          className={styles.principal}
          disabled={!puedeEncolar || encolando}
          onClick={() => void encolar()}
        >
          {encolando ? "Encolando…" : "Encolar a la cola"}
        </button>
      </div>
    </section>
  );
}
