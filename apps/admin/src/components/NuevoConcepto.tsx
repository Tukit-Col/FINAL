// Alta de un CONCEPTO nuevo (P4c bis). El otro brazo de la curación: cuando una
// lista trae algo que el catálogo no cubre con ningún concepto, aquí nace el
// concepto (el código C0NN lo autogenera el backend) y después se le encolan sus
// tres niveles con "Agregar útil"/"Agregar libro". Así crece la BD al revisar.
//
// Nombre y categoría obligatorios (validado aquí, en el Route Handler y en el
// origen, §1.4); un nombre duplicado lo rechaza el backend (409) y el mensaje
// que se muestra es el suyo. Al crearlo se avisa al padre para que lo agregue a
// los selectores de concepto sin refrescar la página.

"use client";

import { useState } from "react";
import type { ConceptoCreado, CrearConcepto, TipoItem } from "@tukit/contrato";
import { crearConcepto, FalloCatalogo } from "@/lib/api-catalogo";
import styles from "./CatalogoSpa.module.css";

// Los tipos que un concepto puede llevar (§1.1). El comprable por defecto es
// "util"; el resto se ofrece por si el concepto es de texto, licencia, etc.
const TIPOS: TipoItem[] = [
  "util",
  "texto",
  "libro_libre",
  "licencia_digital",
  "no_comprar",
  "diferido",
  "uniforme",
  "otro",
];

interface Props {
  onCreado: (concepto: ConceptoCreado) => void;
}

export default function NuevoConcepto({ onCreado }: Props) {
  const [nombre, setNombre] = useState("");
  const [categoria, setCategoria] = useState("");
  const [sinonimos, setSinonimos] = useState("");
  const [tipo, setTipo] = useState<TipoItem>("util");
  const [admitePersonaje, setAdmitePersonaje] = useState(false);

  const [creando, setCreando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const puedeCrear = nombre.trim().length > 0 && categoria.trim().length > 0;

  async function crear() {
    setError(null);
    setExito(null);
    if (!puedeCrear) {
      setError("El concepto necesita al menos un nombre canónico y una categoría.");
      return;
    }
    setCreando(true);
    try {
      const cuerpo: CrearConcepto = {
        nombre_canonico: nombre.trim(),
        categoria: categoria.trim(),
        sinonimos: sinonimos.trim() || undefined,
        tipo_item: tipo,
        admite_personaje: admitePersonaje,
      };
      const creado = await crearConcepto(cuerpo);
      setExito(
        `Creado ${creado.codigo} · ${creado.nombre_canonico}. Ya podés encolarle útiles o libros.`,
      );
      setNombre("");
      setCategoria("");
      setSinonimos("");
      onCreado(creado);
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos crear el concepto.");
    } finally {
      setCreando(false);
    }
  }

  return (
    <section className={styles.spa}>
      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      <p className={styles.nota}>
        Creá el concepto acá y luego encolá sus niveles (económico/confiable/premium) en «Agregar
        útil» o «Agregar libro». El código lo asigna el sistema.
      </p>

      <div className={styles.rejilla}>
        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor="nc-nombre">Nombre canónico</label>
          <input
            id="nc-nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="p. ej. Cartuchera de tela"
          />
        </div>

        <div className={styles.campo}>
          <label htmlFor="nc-categoria">Categoría</label>
          <input
            id="nc-categoria"
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
            placeholder="p. ej. papeleria"
          />
        </div>

        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor="nc-sinonimos">Sinónimos (separados por |)</label>
          <input
            id="nc-sinonimos"
            value={sinonimos}
            onChange={(e) => setSinonimos(e.target.value)}
            placeholder="estuche | lapicera"
          />
        </div>

        <div className={styles.campo}>
          <label htmlFor="nc-tipo">Tipo</label>
          <select id="nc-tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoItem)}>
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.campo}>
          <label htmlFor="nc-personaje">
            <input
              id="nc-personaje"
              type="checkbox"
              checked={admitePersonaje}
              onChange={(e) => setAdmitePersonaje(e.target.checked)}
            />{" "}
            Admite personaje
          </label>
        </div>
      </div>

      <div className={styles.acciones}>
        <button
          type="button"
          className={styles.principal}
          disabled={!puedeCrear || creando}
          onClick={() => void crear()}
        >
          {creando ? "Creando…" : "Crear concepto"}
        </button>
      </div>
    </section>
  );
}
