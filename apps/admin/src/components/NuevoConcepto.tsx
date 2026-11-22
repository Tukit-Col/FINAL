"use client";

import { useId, useState } from "react";
import type { ConceptoCreado, CrearConcepto, TipoItem } from "@tukit/contrato";
import { crearConcepto, FalloCatalogo } from "@/lib/api-catalogo";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

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
  nombreInicial?: string;
  atributosConocidos?: string[];
  categoriasConocidas?: string[];
  compacto?: boolean;
  onCancelar?: () => void;
}

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
          <Desplegable
            id={`${id}-tipo`}
            tamano="compacto"
            opciones={TIPOS.map((t) => ({ valor: t, texto: t }))}
            valor={tipo}
            onCambio={(t) => setTipo(t as TipoItem)}
          />
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
  const [escribiendo, setEscribiendo] = useState(false);
  const [borrador, setBorrador] = useState("");
  const conCampo = escribiendo || sugerencias.length === 0;

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
        <Desplegable
          id={id}
          tamano="compacto"
          buscable={sugerencias.length > 12}
          textoVacio={valores.length ? "Agregar otro…" : "Elegir atributo…"}
          opciones={[
            ...sugerencias.map((a) => ({ valor: a, texto: a })),
            { valor: OTRO_ATRIBUTO, texto: "Otro (escribir)…" },
          ]}
          valor=""
          onCambio={(elegido) => {
            if (elegido === OTRO_ATRIBUTO) setEscribiendo(true);
            else if (elegido) onAgregar(elegido);
          }}
        />
      )}
      <span className={styles.ayudaCampo}>{ayuda}</span>
    </div>
  );
}
