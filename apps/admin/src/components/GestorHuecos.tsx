"use client";

// Gestor de huecos de catálogo. Cada concepto sin cobertura se puede expandir
// y dar de alta un producto con `altaProducto()` — la MISMA mutación del
// contrato que usa AD-07 en la revisión, aquí sin línea de por medio (el
// contrato admite `altaProducto` sin trabajo/item: solo agrega al catálogo).
//
// El precio se valida con el mismo `leerPesos()` que AD-07, por la misma razón:
// el dinero es entero (§1.4) y `18.900` es ambiguo entre países. No se duplica
// la regla, se importa.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, PackageX, Layers, Check } from "lucide-react";
import type { Nivel } from "@tukit/contrato";
import { formatearPesos } from "@tukit/contrato";
import { altaProducto, FalloApi } from "@/lib/api-navegador";
import { leerPesos } from "./AltaProducto";
import styles from "./GestorHuecos.module.css";

export interface Hueco {
  codigo: string;
  nombre: string;
  categoria: string;
  demanda: number;
  productos: number;
}

interface Props {
  huecos: Hueco[];
  parciales: Hueco[];
}

const NIVELES: readonly Nivel[] = ["economico", "confiable", "premium"];

// Formulario de alta acotado a un concepto. Es hermano del AD-07 pero más
// pequeño: aquí no hay línea que resolver, solo se llena el catálogo.
function AltaConcepto({ codigo, alTerminar }: { codigo: string; alTerminar: () => void }) {
  const router = useRouter();
  const [nombre, setNombre] = useState("");
  const [marca, setMarca] = useState("");
  const [nivel, setNivel] = useState<Nivel>("confiable");
  const [personaje, setPersonaje] = useState("");
  const [tienda, setTienda] = useState("");
  const [precioCrudo, setPrecioCrudo] = useState("");
  const [url, setUrl] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lectura = leerPesos(precioCrudo);
  const precio = lectura.valor;

  async function alEnviar(evento: React.FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setError(null);
    if (precio === null) {
      setError(lectura.error);
      return;
    }
    if (!nombre.trim() || !tienda.trim()) {
      setError("Nombre y tienda son obligatorios.");
      return;
    }
    setEnviando(true);
    try {
      await altaProducto({
        concepto: codigo,
        nombre: nombre.trim(),
        marca: marca.trim() || null,
        nivel,
        personaje: personaje.trim() || null,
        imagen_url: null,
        tienda: tienda.trim(),
        precio,
        ...(url.trim() ? { url: url.trim() } : {}),
        // Sin trabajo/item: solo agrega al catálogo, no resuelve ninguna línea.
      });
      alTerminar();
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos dar de alta el producto.");
    } finally {
      setEnviando(false);
    }
  }

  const prefijo = `hueco-${codigo}`;

  return (
    <form className={styles.alta} onSubmit={(e) => void alEnviar(e)}>
      <div className={styles.rejilla}>
        <p className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${prefijo}-nombre`}>Nombre del producto</label>
          <input
            id={`${prefijo}-nombre`}
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-marca`}>Marca o editorial</label>
          <input id={`${prefijo}-marca`} value={marca} onChange={(e) => setMarca(e.target.value)} />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-nivel`}>Nivel</label>
          <select
            id={`${prefijo}-nivel`}
            value={nivel}
            onChange={(e) => setNivel(e.target.value as Nivel)}
          >
            {NIVELES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-personaje`}>Personaje</label>
          <input
            id={`${prefijo}-personaje`}
            value={personaje}
            onChange={(e) => setPersonaje(e.target.value)}
            placeholder="spiderman"
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-tienda`}>Tienda</label>
          <input
            id={`${prefijo}-tienda`}
            value={tienda}
            onChange={(e) => setTienda(e.target.value)}
            placeholder="panamericana"
            required
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-precio`}>Precio en pesos enteros</label>
          <input
            id={`${prefijo}-precio`}
            value={precioCrudo}
            onChange={(e) => setPrecioCrudo(e.target.value)}
            inputMode="numeric"
            autoComplete="off"
            placeholder="18900"
            aria-describedby={`${prefijo}-precio-ayuda`}
          />
          <span
            id={`${prefijo}-precio-ayuda`}
            className={
              precio === null && precioCrudo.trim() !== ""
                ? `${styles.ayuda} ${styles.ayudaError}`
                : styles.ayuda
            }
          >
            {precioCrudo.trim() === ""
              ? "Sin puntos ni comas."
              : precio === null
                ? lectura.error
                : formatearPesos(precio)}
          </span>
        </p>
        <p className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${prefijo}-url`}>URL en la tienda</label>
          <input
            id={`${prefijo}-url`}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
            type="url"
          />
        </p>
      </div>

      {error ? <p className={styles.error}>{error}</p> : null}

      <div className={styles.botonera}>
        <button type="submit" className={styles.principal} disabled={enviando || precio === null}>
          Dar de alta en catálogo
        </button>
      </div>
    </form>
  );
}

function Fila({ hueco }: { hueco: Hueco }) {
  const [abierto, setAbierto] = useState(false);
  const [hecho, setHecho] = useState(false);

  return (
    <li className={`${styles.fila} ${abierto ? styles.filaAbierta : ""}`}>
      <button
        type="button"
        className={styles.filaCabecera}
        aria-expanded={abierto}
        onClick={() => setAbierto((v) => !v)}
      >
        <code className={styles.codigo}>{hueco.codigo}</code>
        <span className={styles.nombre}>{hueco.nombre}</span>
        <span className={styles.categoria}>{hueco.categoria}</span>
        <span className={`${styles.demanda} cifra`} title="Frecuencia de demanda">
          {hueco.demanda}
        </span>
        {hecho ? (
          <span className={styles.hecho}>
            <Check size={13} strokeWidth={3} aria-hidden="true" /> dado de alta
          </span>
        ) : (
          <ChevronDown
            size={16}
            strokeWidth={2.4}
            aria-hidden="true"
            className={styles.chevron}
          />
        )}
      </button>
      {abierto ? (
        <div className={styles.cuerpo}>
          <AltaConcepto
            codigo={hueco.codigo}
            alTerminar={() => {
              setHecho(true);
              setAbierto(false);
            }}
          />
        </div>
      ) : null}
    </li>
  );
}

export default function GestorHuecos({ huecos, parciales }: Props) {
  return (
    <div className={styles.gestor}>
      <section className={styles.grupo}>
        <header className={styles.grupoCabecera}>
          <PackageX size={17} strokeWidth={2.2} aria-hidden="true" />
          <h2>Sin ningún producto</h2>
          <span className={styles.grupoConteo}>{huecos.length}</span>
        </header>
        {huecos.length === 0 ? (
          <p className={styles.grupoVacio}>Ninguno: todos los conceptos tienen algo.</p>
        ) : (
          <ul className={styles.lista}>
            {huecos.map((h) => (
              <Fila key={h.codigo} hueco={h} />
            ))}
          </ul>
        )}
      </section>

      <section className={styles.grupo}>
        <header className={styles.grupoCabecera}>
          <Layers size={17} strokeWidth={2.2} aria-hidden="true" />
          <h2>Cobertura parcial (faltan niveles)</h2>
          <span className={styles.grupoConteo}>{parciales.length}</span>
        </header>
        {parciales.length === 0 ? (
          <p className={styles.grupoVacio}>Ninguno: los que tienen productos tienen los tres niveles.</p>
        ) : (
          <ul className={styles.lista}>
            {parciales.map((h) => (
              <Fila key={h.codigo} hueco={h} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
