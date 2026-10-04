// Alta de un CONCEPTO nuevo (P4c bis). El otro brazo de la curación: cuando una
// lista trae algo que el catálogo no cubre con ningún concepto, aquí nace el
// concepto (el código C0NN lo autogenera el backend) y después se le encolan sus
// tres niveles con "Agregar útil"/"Agregar libro". Así crece la BD al revisar.
//
// Vive en dos lugares: la pestaña «Nuevo concepto» del catálogo y, en modo
// `compacto`, dentro del editor de un renglón del revisor de listas —ahí nace
// con el texto del renglón como nombre y, al crearlo, queda elegido—.
//
// Además de nombre, categoría y sinónimos, el concepto declara sus atributos en
// sus dos papeles (ver `demanda_atributos` en el catálogo):
//   - los que FILTRAN: un producto que no cumple se descarta (un cuaderno
//     cuadriculado no pasa por uno rayado);
//   - los que INFORMAN: se muestran al acudiente pero no descartan nada (la
//     talla de una bata, que ninguna lista pide).
// Un mismo atributo no puede estar en las dos listas: pasarlo a una lo saca de
// la otra.
//
// Nombre y categoría obligatorios (validado aquí, en el Route Handler y en el
// origen, §1.4); un nombre duplicado lo rechaza el backend (409) y el mensaje
// que se muestra es el suyo.

"use client";

import { useId, useState } from "react";
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
  /** Nombre con que arranca el formulario (el texto del renglón, en el revisor). */
  nombreInicial?: string;
  /** Nombres de atributo que ya usan otros conceptos, para sugerirlos. */
  atributosConocidos?: string[];
  /** Categorías existentes, para sugerirlas y no partir el vocabulario. */
  categoriasConocidas?: string[];
  /** Versión embebida: sin la nota larga y con botón de cancelar. */
  compacto?: boolean;
  onCancelar?: () => void;
}

/** La forma del corpus: minúsculas y `_` por espacio. */
function normalizarAtributo(texto: string): string {
  return texto.trim().toLowerCase().replace(/\s+/g, "_");
}

export default function NuevoConcepto({
  onCreado,
  nombreInicial = "",
  atributosConocidos = [],
  categoriasConocidas = [],
  compacto = false,
  onCancelar,
}: Props) {
  const id = useId();
  const [nombre, setNombre] = useState(nombreInicial);
  const [categoria, setCategoria] = useState("");
  const [sinonimos, setSinonimos] = useState("");
  const [tipo, setTipo] = useState<TipoItem>("util");
  const [admitePersonaje, setAdmitePersonaje] = useState(false);
  const [filtran, setFiltran] = useState<string[]>([]);
  const [informan, setInforman] = useState<string[]>([]);

  const [creando, setCreando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const puedeCrear = nombre.trim().length > 0 && categoria.trim().length > 0;

  // Un atributo vive en una sola lista: agregarlo a una lo saca de la otra.
  function agregarA(lista: "filtran" | "informan", atributo: string) {
    if (lista === "filtran") {
      setFiltran((a) => (a.includes(atributo) ? a : [...a, atributo]));
      setInforman((a) => a.filter((x) => x !== atributo));
    } else {
      setInforman((a) => (a.includes(atributo) ? a : [...a, atributo]));
      setFiltran((a) => a.filter((x) => x !== atributo));
    }
  }

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
        atributos_discriminantes: filtran,
        atributos_descriptivos: informan,
      };
      const creado = await crearConcepto(cuerpo);
      setExito(
        compacto
          ? `Creado ${creado.codigo} · ${creado.nombre_canonico}.`
          : `Creado ${creado.codigo} · ${creado.nombre_canonico}. Ya puedes encolarle útiles o libros.`,
      );
      setNombre("");
      setCategoria("");
      setSinonimos("");
      setFiltran([]);
      setInforman([]);
      onCreado(creado);
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos crear el concepto.");
    } finally {
      setCreando(false);
    }
  }

  const listaCategorias = `${id}-categorias`;
  // Lo que ya usan otros conceptos y este todavía no tiene en ninguna lista.
  const sugerenciasAtributo = atributosConocidos.filter(
    (a) => !filtran.includes(a) && !informan.includes(a),
  );

  return (
    <section className={compacto ? styles.conceptoCompacto : styles.spa}>
      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      {compacto ? (
        <p className={styles.nota}>
          <strong>Nuevo concepto.</strong> Al crearlo queda elegido para este renglón.
        </p>
      ) : (
        <p className={styles.nota}>
          Crea el concepto aquí y luego encola sus niveles (económico/confiable/premium) en
          «Agregar útil» o «Agregar libro». El código lo asigna el sistema.
        </p>
      )}

      <div className={styles.rejilla}>
        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${id}-nombre`}>Nombre canónico</label>
          <input
            id={`${id}-nombre`}
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="p. ej. Cartuchera de tela"
          />
        </div>

        <div className={styles.campo}>
          <label htmlFor={`${id}-categoria`}>Categoría</label>
          <input
            id={`${id}-categoria`}
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
            placeholder="p. ej. Cartucheras / Morrales"
            list={listaCategorias}
          />
          <datalist id={listaCategorias}>
            {categoriasConocidas.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>

        <div className={styles.campo}>
          <label htmlFor={`${id}-tipo`}>Tipo</label>
          <select
            id={`${id}-tipo`}
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoItem)}
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${id}-sinonimos`}>Sinónimos (separados por |)</label>
          <input
            id={`${id}-sinonimos`}
            value={sinonimos}
            onChange={(e) => setSinonimos(e.target.value)}
            placeholder="estuche | lapicera"
          />
        </div>

        <EditorAtributos
          titulo="Atributos que filtran"
          ayuda="Si el renglón lo pide y el producto no lo cumple, se descarta. Ej.: rayado, hojas, tamaño."
          valores={filtran}
          sugerencias={sugerenciasAtributo}
          onAgregar={(a) => agregarA("filtran", a)}
          onQuitar={(a) => setFiltran((v) => v.filter((x) => x !== a))}
        />
        <EditorAtributos
          titulo="Atributos informativos"
          ayuda="Se muestran al acudiente pero no descartan productos. Ej.: color, marca, talla."
          valores={informan}
          sugerencias={sugerenciasAtributo}
          onAgregar={(a) => agregarA("informan", a)}
          onQuitar={(a) => setInforman((v) => v.filter((x) => x !== a))}
        />

        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor={`${id}-personaje`} className={styles.casilla}>
            <input
              id={`${id}-personaje`}
              type="checkbox"
              checked={admitePersonaje}
              onChange={(e) => setAdmitePersonaje(e.target.checked)}
            />
            Admite personaje (el kit Fan puede elegir una versión con personaje)
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
        {onCancelar ? (
          <button type="button" className={styles.secundario} onClick={onCancelar}>
            Cancelar
          </button>
        ) : null}
      </div>
    </section>
  );
}

// ------------------------------------------------------- editor de atributos

// Valor de la opción que cambia el menú por un campo de texto.
const OTRO_ATRIBUTO = "__otro__";

function EditorAtributos({
  titulo,
  ayuda,
  valores,
  sugerencias,
  onAgregar,
  onQuitar,
}: {
  titulo: string;
  ayuda: string;
  valores: string[];
  sugerencias: string[];
  onAgregar: (atributo: string) => void;
  onQuitar: (atributo: string) => void;
}) {
  const id = useId();
  // Un menú como el de «Tipo» con los atributos que ya existen; «Otro» lo
  // cambia por un campo para escribir uno nuevo. Sin sugerencias se escribe
  // directo. (Antes era un `datalist`, cuyo desplegable es del navegador y no
  // se parece a ningún otro menú del admin.)
  const [escribiendo, setEscribiendo] = useState(false);
  const [borrador, setBorrador] = useState("");
  const conCampo = escribiendo || sugerencias.length === 0;

  // Agrega lo escrito (puede venir más de uno separado por coma o |).
  function confirmar() {
    for (const parte of borrador.split(/[,|]/)) {
      const atributo = normalizarAtributo(parte);
      if (atributo) onAgregar(atributo);
    }
    setBorrador("");
    setEscribiendo(false);
  }

  return (
    <div className={styles.campo}>
      <label htmlFor={id}>{titulo}</label>
      {valores.length > 0 && (
        <div className={styles.atributoFichas}>
          {valores.map((a) => (
            <span key={a} className={styles.atributoChip}>
              {a}
              <button
                type="button"
                aria-label={`Quitar ${a}`}
                className={styles.atributoQuitar}
                onClick={() => onQuitar(a)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      {conCampo ? (
        <input
          id={id}
          value={borrador}
          autoFocus={escribiendo}
          placeholder="escribe y pulsa Enter"
          onChange={(e) => setBorrador(e.target.value)}
          onBlur={confirmar}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              confirmar();
            } else if (e.key === "Escape") {
              setBorrador("");
              setEscribiendo(false);
            }
          }}
        />
      ) : (
        <select
          id={id}
          value=""
          onChange={(e) => {
            if (e.target.value === OTRO_ATRIBUTO) setEscribiendo(true);
            else if (e.target.value) onAgregar(e.target.value);
          }}
        >
          <option value="">{valores.length ? "Agregar otro…" : "Elegir atributo…"}</option>
          {sugerencias.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
          <option value={OTRO_ATRIBUTO}>Otro (escribir)…</option>
        </select>
      )}
      <span className={styles.ayudaCampo}>{ayuda}</span>
    </div>
  );
}
