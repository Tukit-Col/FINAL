// Alta de un útil, en dos modos: buscar en tienda o escribir a mano.
//
// Decisiones:
// - Buscar en tienda encola el útil con `altaUtil`; el backend vuelve a buscar por `(slug, sku)` para no
//   confiar en un precio que el navegador pudo alterar.
// - Escribir a mano es para lo que la búsqueda no encuentra o para una tienda sin búsqueda en vivo.

"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";
import { NIVELES, ETIQUETA_NIVEL, formatearPesos } from "@tukit/contrato";
import type { CandidatoTienda, Nivel } from "@tukit/contrato";
import { buscarEnTienda, altaUtil, altaUtilManual, FalloCatalogo } from "@/lib/api-catalogo";
import type { OpcionConcepto } from "./PanelReclasificar";
import type { OpcionTienda } from "./SeccionesCatalogo";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

const TIENDAS_BUSCABLES: { slug: string; nombre: string }[] = [
  { slug: "exito", nombre: "Éxito" },
  { slug: "panamericana", nombre: "Panamericana" },
  { slug: "grancentral", nombre: "Gran Central" },
];

type Modo = "buscar" | "manual";

interface Props {
  conceptos: OpcionConcepto[];
  tiendas: OpcionTienda[];
  onEncolado: () => void;
  conceptoInicial?: string;
  consultaInicial?: string;
}

export default function AltaUtil({
  conceptos,
  tiendas,
  onEncolado,
  conceptoInicial,
  consultaInicial,
}: Props) {
  const [modo, setModo] = useState<Modo>("buscar");

  const [concepto, setConcepto] = useState(conceptoInicial ?? "");
  const [nivel, setNivel] = useState<Nivel>("confiable");
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [encolando, setEncolando] = useState(false);

  const [slug, setSlug] = useState(TIENDAS_BUSCABLES[0]!.slug);
  const [consulta, setConsulta] = useState(consultaInicial ?? "");
  const [candidatos, setCandidatos] = useState<CandidatoTienda[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [elegido, setElegido] = useState<CandidatoTienda | null>(null);

  const [nombre, setNombre] = useState("");
  const [precio, setPrecio] = useState("");
  const [slugManual, setSlugManual] = useState(tiendas[0]?.slug ?? "");
  const [sku, setSku] = useState("");
  const [marca, setMarca] = useState("");

  const precioNum = Number(precio);
  const precioValido = Number.isInteger(precioNum) && precioNum > 0;

  function cambiarModo(nuevo: Modo) {
    setModo(nuevo);
    setError(null);
    setExito(null);
  }

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

  async function encolarBuscado() {
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

  const puedeEncolarManual =
    nombre.trim().length > 0 && precioValido && concepto.length > 0 && slugManual.trim().length > 0;

  async function encolarManual() {
    setError(null);
    setExito(null);
    if (!puedeEncolarManual) {
      setError("Revisá nombre, precio (entero en pesos > 0), tienda y concepto.");
      return;
    }
    setEncolando(true);
    try {
      const r = await altaUtilManual({
        concepto,
        nombre: nombre.trim(),
        precio: precioNum,
        slug: slugManual.trim(),
        sku: sku.trim() || undefined,
        marca: marca.trim() || undefined,
        nivel,
      });
      setExito(`Encolado (${r.id_corto}). Revisalo en la cola para aprobarlo.`);
      setNombre("");
      setPrecio("");
      setSku("");
      setMarca("");
      onEncolado();
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos encolar el útil.");
    } finally {
      setEncolando(false);
    }
  }

  return (
    <section className={styles.spa}>
      <div className={styles.pestanas} role="tablist" aria-label="Modo de alta de útil">
        <button
          type="button"
          role="tab"
          className={`${styles.pestana} ${modo === "buscar" ? styles.pestanaActiva : ""}`}
          aria-selected={modo === "buscar"}
          onClick={() => cambiarModo("buscar")}
        >
          Buscar en tienda
        </button>
        <button
          type="button"
          role="tab"
          className={`${styles.pestana} ${modo === "manual" ? styles.pestanaActiva : ""}`}
          aria-selected={modo === "manual"}
          onClick={() => cambiarModo("manual")}
        >
          Escribir a mano
        </button>
      </div>

      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      {modo === "buscar" && (
        <>
          <div className={styles.buscadorFila}>
            <div className={styles.campo}>
              <label htmlFor="au-tienda">Tienda</label>
              <Desplegable
                id="au-tienda"
                tamano="compacto"
                buscable={TIENDAS_BUSCABLES.length > 12}
                opciones={TIENDAS_BUSCABLES.map((t) => ({ valor: t.slug, texto: t.nombre }))}
                valor={slug}
                onCambio={setSlug}
              />
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
              Buscá un útil en la tienda para ver candidatos y encolar uno. Si no aparece, escribilo
              a mano.
            </p>
          )}

          {candidatos.length > 0 && (
            <div className={styles.rejillaProductos}>
              {candidatos.map((c) => (
                <button
                  key={`${c.slug}:${c.sku}`}
                  type="button"
                  className={`${styles.tarjeta} ${elegido?.sku === c.sku ? styles.tarjetaActiva : ""}`}
                  aria-pressed={elegido?.sku === c.sku}
                  onClick={() => {
                    setElegido(c);
                    setExito(null);
                  }}
                >
                  {c.imagen_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img className={styles.tarjetaFoto} src={c.imagen_url} alt="" />
                  ) : (
                    <span className={styles.tarjetaFotoVacia}>
                      <ImageOff size={28} aria-hidden="true" />
                    </span>
                  )}

                  {!c.disponible && (
                    <div className={styles.tarjetaPildoras}>
                      <span className={styles.sinDato}>agotado</span>
                    </div>
                  )}

                  <div className={styles.tarjetaNombre}>{c.nombre}</div>
                  <div className={styles.skuMono}>{c.sku}</div>

                  <div className={styles.tarjetaPie}>
                    <span className={styles.tarjetaPrecio}>{formatearPesos(c.precio)}</span>
                    <span className={styles.tarjetaMeta}>
                      {c.marca ? <span>{c.marca}</span> : null}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {elegido && (
            <div className={styles.panel}>
              <header className={styles.panelCabecera}>
                <h2>{elegido.nombre}</h2>
                <span className={styles.panelSku}>
                  {elegido.sku} · {formatearPesos(elegido.precio)}
                  {elegido.marca ? ` · ${elegido.marca}` : ""}
                </span>
              </header>
              <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
                <div className={styles.campo}>
                  <label htmlFor="au-concepto">Concepto</label>
                  <Desplegable
                    id="au-concepto"
                    tamano="compacto"
                    buscable
                    textoVacio="— elegir concepto —"
                    opciones={conceptos.map((op) => ({ valor: op.codigo, texto: op.nombre }))}
                    valor={concepto}
                    onCambio={setConcepto}
                  />
                </div>
                <label className={styles.bandera}>
                  Nivel sugerido
                  <Desplegable
                    tamano="compacto"
                    enLinea
                    opciones={NIVELES.map((n) => ({ valor: n, texto: ETIQUETA_NIVEL[n] }))}
                    valor={nivel}
                    onCambio={(v) => setNivel(v as Nivel)}
                  />
                </label>
                <button
                  type="button"
                  className={styles.principal}
                  disabled={!concepto || encolando}
                  onClick={() => void encolarBuscado()}
                >
                  {encolando ? "Encolando…" : "Encolar a la cola"}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {modo === "manual" && (
        <>
          <p className={styles.nota}>
            Para lo que la búsqueda no encuentra. Escribí nombre, precio (entero en pesos) y tienda;
            el SKU y la marca son opcionales.
          </p>

          <div className={styles.rejilla}>
            <div className={`${styles.campo} ${styles.campoAncho}`}>
              <label htmlFor="aum-nombre">Nombre</label>
              <input
                id="aum-nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Cuaderno cosido 100 hojas"
              />
            </div>

            <div className={styles.campo}>
              <label htmlFor="aum-precio">Precio (pesos)</label>
              <input
                id="aum-precio"
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
              <label htmlFor="aum-tienda">Tienda</label>
              <input
                id="aum-tienda"
                list="aum-tiendas"
                value={slugManual}
                onChange={(e) => setSlugManual(e.target.value)}
                placeholder="elegí o escribí un slug"
              />
              <datalist id="aum-tiendas">
                {tiendas.map((t) => (
                  <option key={t.slug} value={t.slug}>
                    {t.nombre}
                  </option>
                ))}
              </datalist>
            </div>

            <div className={styles.campo}>
              <label htmlFor="aum-sku">SKU (opcional)</label>
              <input id="aum-sku" value={sku} onChange={(e) => setSku(e.target.value)} />
            </div>

            <div className={styles.campo}>
              <label htmlFor="aum-marca">Marca (opcional)</label>
              <input id="aum-marca" value={marca} onChange={(e) => setMarca(e.target.value)} />
            </div>

            <div className={styles.campo}>
              <label htmlFor="aum-concepto">Concepto</label>
              <Desplegable
                id="aum-concepto"
                tamano="compacto"
                buscable
                textoVacio="— elegir concepto —"
                opciones={conceptos.map((op) => ({ valor: op.codigo, texto: op.nombre }))}
                valor={concepto}
                onCambio={setConcepto}
              />
            </div>

            <div className={styles.campo}>
              <label htmlFor="aum-nivel">Nivel sugerido</label>
              <Desplegable
                id="aum-nivel"
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
              disabled={!puedeEncolarManual || encolando}
              onClick={() => void encolarManual()}
            >
              {encolando ? "Encolando…" : "Encolar a la cola"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
