"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { LineaKit, Nivel } from "@tukit/contrato";
import { formatearPesos } from "@tukit/contrato";
import { altaProducto, FalloApi } from "@/lib/api-navegador";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  linea: LineaKit;
  alTerminar: (sku: string) => void;
}

const NIVELES: readonly Nivel[] = ["economico", "confiable", "premium"];

interface Lectura {
  valor: number | null;
  error: string | null;
}

function malo(error: string): Lectura {
  return { valor: null, error };
}

export function leerPesos(crudo: string): Lectura {
  const limpio = crudo.trim().replace(/[\s$]/g, "");
  if (!limpio) return malo("Escribe el precio.");
  if (/[.,]/.test(limpio)) {
    return malo(
      "El precio va en pesos enteros, sin puntos ni comas: escribe 18900, no 18.900 ni 18900,00.",
    );
  }
  if (!/^\d+$/.test(limpio)) return malo("El precio solo admite dígitos.");
  const valor = Number(limpio);
  if (!Number.isSafeInteger(valor) || valor <= 0) {
    return malo("El precio tiene que ser un entero positivo en pesos.");
  }
  return { valor, error: null };
}

export default function AltaProducto({ trabajoId, linea, alTerminar }: Props) {
  const router = useRouter();

  const [concepto, setConcepto] = useState(linea.concepto ?? "");
  const [nombre, setNombre] = useState(linea.edicion?.titulo ?? linea.descripcion);
  const [marca, setMarca] = useState(linea.edicion?.editorial ?? "");
  const [nivel, setNivel] = useState<Nivel>("confiable");
  const [personaje, setPersonaje] = useState("");
  const [imagenUrl, setImagenUrl] = useState("");
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
    if (!concepto.trim() || !nombre.trim() || !tienda.trim()) {
      setError("Concepto, nombre y tienda son obligatorios.");
      return;
    }

    setEnviando(true);
    try {
      const { sku } = await altaProducto({
        concepto: concepto.trim(),
        nombre: nombre.trim(),
        marca: marca.trim() || null,
        nivel,
        personaje: personaje.trim() || null,
        imagen_url: imagenUrl.trim() || null,
        tienda: tienda.trim(),
        precio,
        ...(url.trim() ? { url: url.trim() } : {}),
        trabajo_id: trabajoId,
        item_id: linea.item_id,
      });
      alTerminar(sku);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos dar de alta el producto.");
    } finally {
      setEnviando(false);
    }
  }

  const prefijo = `alta-${linea.item_id}`;

  return (
    <form className={styles.alta} onSubmit={(evento) => void alEnviar(evento)}>
      <h4>Alta manual del producto (AD-07)</h4>
      <p className={styles.altaBajada}>
        Queda asignado a <code>{linea.item_id}</code> y la línea pasa a validada.
      </p>

      <div className={styles.rejilla}>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-concepto`}>Concepto</label>
          <input
            id={`${prefijo}-concepto`}
            value={concepto}
            onChange={(evento) => setConcepto(evento.target.value)}
            placeholder="C012 texto de lenguaje"
            required
          />
        </p>
        <p className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${prefijo}-nombre`}>Nombre del producto</label>
          <input
            id={`${prefijo}-nombre`}
            value={nombre}
            onChange={(evento) => setNombre(evento.target.value)}
            required
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-marca`}>Marca o editorial</label>
          <input
            id={`${prefijo}-marca`}
            value={marca}
            onChange={(evento) => setMarca(evento.target.value)}
            placeholder="Norma"
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-nivel`}>Nivel</label>
          <select
            id={`${prefijo}-nivel`}
            value={nivel}
            onChange={(evento) => setNivel(evento.target.value as Nivel)}
          >
            {NIVELES.map((valor) => (
              <option key={valor} value={valor}>
                {valor}
              </option>
            ))}
          </select>
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-personaje`}>Personaje</label>
          <input
            id={`${prefijo}-personaje`}
            value={personaje}
            onChange={(evento) => setPersonaje(evento.target.value)}
            placeholder="spiderman"
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-tienda`}>Tienda</label>
          <input
            id={`${prefijo}-tienda`}
            value={tienda}
            onChange={(evento) => setTienda(evento.target.value)}
            placeholder="panamericana"
            required
          />
        </p>
        <p className={styles.campo}>
          <label htmlFor={`${prefijo}-precio`}>Precio en pesos enteros</label>
          <input
            id={`${prefijo}-precio`}
            value={precioCrudo}
            onChange={(evento) => setPrecioCrudo(evento.target.value)}
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
              : (precio === null ? lectura.error : formatearPesos(precio))}
          </span>
        </p>
        <p className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${prefijo}-imagen`}>URL de la imagen</label>
          <input
            id={`${prefijo}-imagen`}
            value={imagenUrl}
            onChange={(evento) => setImagenUrl(evento.target.value)}
            placeholder="https://..."
            type="url"
          />
        </p>
        <p className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${prefijo}-url`}>URL en la tienda</label>
          <input
            id={`${prefijo}-url`}
            value={url}
            onChange={(evento) => setUrl(evento.target.value)}
            placeholder="https://..."
            type="url"
          />
        </p>
      </div>

      {error ? <p className={styles.error}>{error}</p> : null}

      <div className={styles.botonera}>
        <button type="submit" className={styles.principal} disabled={enviando || precio === null}>
          Dar de alta y asignar
        </button>
      </div>
    </form>
  );
}
