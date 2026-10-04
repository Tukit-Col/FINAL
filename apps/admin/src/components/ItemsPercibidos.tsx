"use client";

// Región 3 del revisor de listas (P4): los renglones de una versión importada
// (`revisionLista`), con su concepto ya emparejado, sus candidatos/confianza
// (las `propuestas`) y —por línea— el control de adquisición directa del colegio
// (modo + instrucción libre). WIRED contra los Route Handlers de esta app.
//
// ALCANCE: ADD + EDIT, nunca borrado duro desde la revisión (el borrado vive en
// /cola sobre el producto de catálogo). Editar un renglón manda un PATCH con solo
// lo que cambió; dar de alta uno manda un POST. Tras cada escritura se hace
// `router.refresh()` para que el Server Component vuelva a leer `revisionLista`.
//
// Si ningún concepto le sirve al renglón, se crea ahí mismo (con sus atributos
// que filtran e informan) en vez de ir al catálogo y volver: nace con el texto
// del renglón como nombre, entra a la lista de conceptos de toda la pantalla y
// queda elegido en el editor, listo para «Guardar cambios».

import { useState } from "react";
import { useRouter } from "next/navigation";
import type {
  ConceptoCreado,
  ItemListaEditable,
  ItemRevision,
  ModoAdquisicion,
  PropuestaRevision,
} from "@tukit/contrato";
import { agregarItemLista, editarItemLista, quitarItemLista, FalloListas } from "@/lib/api-listas";
import type { OpcionConcepto } from "./PanelReclasificar";
import NuevoConcepto from "./NuevoConcepto";
import type { VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import styles from "@/app/onboarding/Onboarding.module.css";

// Los modos de adquisición directa del colegio que el §1.1.1 lista y que el
// revisor puede fijar por línea. `mercado_abierto`/`libro_libre` no están aquí:
// esos son "se compra normal", no "el colegio lo entrega".
const MODOS_DIRECTOS: { valor: ModoAdquisicion; etiqueta: string }[] = [
  { valor: "venta_directa_editorial", etiqueta: "Venta directa de la editorial" },
  { valor: "edicion_exclusiva", etiqueta: "Edición exclusiva del colegio" },
  { valor: "plataforma", etiqueta: "Plataforma / licencia digital" },
  { valor: "diferido", etiqueta: "Diferido (lo pide durante el año)" },
];

const VALORES_DIRECTOS = new Set<string>(MODOS_DIRECTOS.map((m) => m.valor));

interface Props {
  versionId: string;
  revisada: boolean;
  items: ItemRevision[];
  propuestas: PropuestaRevision[];
  conceptos: OpcionConcepto[];
  vocabulario: VocabularioConceptos;
}

// Los candidatos de un renglón. La llave fiable es `item_id` (1:1 con el
// renglón): una lista pide dos renglones iguales ("Cuaderno ferrocarril" dos
// veces) y agrupar por texto le colgaba a uno los candidatos del otro. Se cae a
// `texto_origen` solo para propuestas viejas anteriores al vínculo (item_id null).
function candidatosDe(item: ItemRevision, propuestas: PropuestaRevision[]): PropuestaRevision[] {
  return propuestas.filter((p) =>
    p.item_id != null ? p.item_id === item.id : p.texto_origen === item.texto_original,
  );
}

export default function ItemsPercibidos({
  versionId,
  revisada,
  items,
  propuestas,
  conceptos: conceptosIniciales,
  vocabulario,
}: Props) {
  // En estado para que un concepto creado desde un renglón aparezca enseguida
  // en el selector de todos los demás, sin refrescar.
  const [conceptos, setConceptos] = useState(conceptosIniciales);

  function alCrearConcepto(creado: ConceptoCreado) {
    setConceptos((previos) =>
      [...previos, { codigo: creado.codigo, nombre: creado.nombre_canonico }].sort((a, b) =>
        a.nombre.localeCompare(b.nombre),
      ),
    );
  }

  if (items.length === 0) {
    return <p className={styles.pendienteContrato}>El modelo no itemizó ninguna línea.</p>;
  }

  return (
    <div className={styles.items}>
      {items.map((item) => (
        <RenglonEditable
          key={item.id}
          versionId={versionId}
          revisada={revisada}
          item={item}
          candidatos={candidatosDe(item, propuestas)}
          conceptos={conceptos}
          vocabulario={vocabulario}
          onConceptoCreado={alCrearConcepto}
        />
      ))}
      <AltaRenglon versionId={versionId} revisada={revisada} />
    </div>
  );
}

// ------------------------------------------------------------- renglón editable

function RenglonEditable({
  versionId,
  revisada,
  item,
  candidatos,
  conceptos,
  vocabulario,
  onConceptoCreado,
}: {
  versionId: string;
  revisada: boolean;
  item: ItemRevision;
  candidatos: PropuestaRevision[];
  conceptos: OpcionConcepto[];
  vocabulario: VocabularioConceptos;
  onConceptoCreado: (creado: ConceptoCreado) => void;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [creandoConcepto, setCreandoConcepto] = useState(false);
  const [dividiendo, setDividiendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // La lectura de Gemini, corregible sin tener que dividir el renglon.
  const [texto, setTexto] = useState(item.texto_original);
  const [concepto, setConcepto] = useState(item.concepto_codigo ?? "");
  const [cantidad, setCantidad] = useState(String(item.cantidad));
  // El select solo distingue los modos directos; cualquier otro modo guardado
  // (mercado_abierto, libro_libre, diferido) se muestra como la opción vacía.
  const modoGuardado = VALORES_DIRECTOS.has(item.modo_adquisicion ?? "") ? item.modo_adquisicion! : "";
  const [modo, setModo] = useState<ModoAdquisicion | "">(modoGuardado);
  const [instruccion, setInstruccion] = useState(item.instruccion_colegio ?? "");

  // Adquisición directa del colegio: el colegio lo entrega, no se compra. No
  // tiene sentido mostrar concepto ni candidatos ("no lo ofrecemos"). Se toma
  // del estado del editor (lo que el revisor está fijando), para que el
  // colapso reaccione al elegir el modo sin recargar.
  const esDirecto = VALORES_DIRECTOS.has(modo);

  // La confianza más alta entre los candidatos, para el semáforo del renglón.
  const confianza =
    !esDirecto && candidatos.length > 0 ? Math.max(...candidatos.map((c) => c.puntaje)) : null;

  async function eliminar() {
    if (!confirm(`¿Quitar "${item.texto_original}" de la lista?`)) return;
    setGuardando(true);
    setError(null);
    try {
      await quitarItemLista(versionId, item.id);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo quitar el ítem.");
      setGuardando(false);
    }
  }

  async function guardar() {
    if (!texto.trim()) {
      setError("El renglón necesita un texto. Para quitarlo, usa Eliminar.");
      return;
    }
    setGuardando(true);
    setError(null);
    // Solo se manda lo que cambió (todos opcionales). El modo vacío = mercado
    // abierto: la columna es NOT NULL, así que se manda el valor explícito.
    const cambios: ItemListaEditable = {};
    if (texto.trim() !== item.texto_original) cambios.texto_original = texto.trim();
    if (concepto !== (item.concepto_codigo ?? "")) cambios.concepto = concepto || null;
    const cantidadNum = Number(cantidad);
    if (Number.isFinite(cantidadNum) && cantidadNum !== item.cantidad) cambios.cantidad = cantidadNum;
    if (modo !== modoGuardado) cambios.modo_adquisicion = modo || "mercado_abierto";
    if (instruccion !== (item.instruccion_colegio ?? ""))
      cambios.instruccion_colegio = instruccion || null;

    try {
      await editarItemLista(versionId, item.id, cambios);
      setAbierto(false);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo guardar el ítem.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={styles.item}>
      <div className={styles.itemLinea}>
        <span className={styles.itemTexto}>{item.texto_original}</span>
        {confianza !== null ? (
          <span className={`${styles.confianza} ${confianza < 0.6 ? styles.confianzaBaja : ""}`}>
            {Math.round(confianza * 100)}%
          </span>
        ) : null}
      </div>
      <div className={styles.itemMeta}>
        <span>cantidad: {item.cantidad}</span>
        <span>{item.unidad ?? "unidad"}</span>
      </div>
      {esDirecto ? (
        <span className={`${styles.concepto} ${styles.conceptoRevision}`}>
          El colegio lo entrega — no se surte ni se empareja con producto.
        </span>
      ) : (
        <>
          <span
            className={`${styles.concepto} ${item.concepto_codigo ? "" : styles.conceptoRevision}`}
          >
            {item.concepto_codigo
              ? `Concepto: ${item.concepto_nombre} (${item.concepto_codigo})`
              : "Sin concepto — va a revisión"}
          </span>
          {!item.concepto_codigo && !revisada && !creandoConcepto ? (
            <button
              type="button"
              className={styles.botonMini}
              onClick={() => {
                setAbierto(true);
                setCreandoConcepto(true);
              }}
            >
              + Crear concepto para este renglón
            </button>
          ) : null}

          {candidatos.length > 0 ? (
            <div className={styles.candidatos}>
              {candidatos.map((c) => (
                <div key={c.id} className={styles.candidato}>
                  <span>{c.nombre}</span>
                  <span className={styles.candidatoPuntaje}>{Math.round(c.puntaje * 100)}%</span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      )}

      <div className={styles.itemAcciones}>
        <button
          type="button"
          className={styles.botonMini}
          onClick={() => {
            setAbierto((v) => !v);
            setCreandoConcepto(false);
          }}
          disabled={revisada}
        >
          {abierto ? "Cerrar" : "Editar"}
        </button>
        <button
          type="button"
          className={styles.botonMini}
          onClick={() => setDividiendo((v) => !v)}
          disabled={revisada || guardando}
          title="Partir este renglón en varios (p. ej. «cuaderno y lápiz» → dos líneas)"
        >
          {dividiendo ? "Cerrar" : "Dividir"}
        </button>
        <button
          type="button"
          className={styles.botonMini}
          onClick={eliminar}
          disabled={revisada || guardando}
          title="Quitar este renglón de la lista"
        >
          Eliminar
        </button>
      </div>

      {dividiendo ? (
        <DividirRenglon
          versionId={versionId}
          item={item}
          onListo={() => setDividiendo(false)}
        />
      ) : null}

      {abierto ? (
        <div className={styles.editor}>
          <label className={styles.campo}>
            <span>Texto del renglón</span>
            <input value={texto} onChange={(e) => setTexto(e.target.value)} disabled={guardando} />
          </label>
          <label className={styles.campo}>
            <span>Concepto (vacío = sin concepto)</span>
            <span className={styles.conceptoFila}>
              <select
                value={concepto}
                onChange={(e) => setConcepto(e.target.value)}
                disabled={guardando}
              >
                <option value="">— sin concepto —</option>
                {conceptos.map((c) => (
                  <option key={c.codigo} value={c.codigo}>
                    {c.nombre} ({c.codigo})
                  </option>
                ))}
              </select>
              {!creandoConcepto ? (
                <button
                  type="button"
                  className={styles.botonMini}
                  onClick={() => setCreandoConcepto(true)}
                  disabled={guardando}
                  title="Ningún concepto le sirve: crear uno nuevo"
                >
                  + Nuevo
                </button>
              ) : null}
            </span>
          </label>
          {creandoConcepto ? (
            <NuevoConcepto
              compacto
              nombreInicial={item.texto_original}
              atributosConocidos={vocabulario.atributos}
              categoriasConocidas={vocabulario.categorias}
              onCancelar={() => setCreandoConcepto(false)}
              onCreado={(creado) => {
                onConceptoCreado(creado);
                setConcepto(creado.codigo);
                setCreandoConcepto(false);
              }}
            />
          ) : null}
          <label className={styles.campo}>
            <span>Cantidad</span>
            <input
              type="number"
              min={0}
              value={cantidad}
              onChange={(e) => setCantidad(e.target.value)}
              disabled={guardando}
            />
          </label>
          <label className={styles.campo}>
            <span>Cómo se adquiere</span>
            <select
              value={modo}
              onChange={(e) => setModo(e.target.value as ModoAdquisicion | "")}
              disabled={guardando}
            >
              <option value="">Mercado abierto (se compra normal)</option>
              {MODOS_DIRECTOS.map((m) => (
                <option key={m.valor} value={m.valor}>
                  {m.etiqueta}
                </option>
              ))}
            </select>
          </label>
          {esDirecto ? (
            <label className={styles.campo}>
              <span>Instrucción del colegio</span>
              <input
                value={instruccion}
                onChange={(e) => setInstruccion(e.target.value)}
                placeholder="Ej. se compra en la papelería del colegio"
                disabled={guardando}
              />
            </label>
          ) : null}
          {error ? <p className={styles.itemError}>{error}</p> : null}
          <div className={styles.itemAcciones}>
            <button
              type="button"
              className={styles.principal}
              onClick={guardar}
              disabled={guardando}
            >
              {guardando ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// -------------------------------------------------------------- dividir renglón
//
// Partir un renglón que el modelo juntó ("Cuaderno cuadriculado y lápiz") en
// varios. No hay endpoint de "split": se reusan los que ya existen (POST agrega,
// DELETE quita). Se AGREGAN primero todas las partes y solo al final se QUITA el
// original, para que una falla a mitad no borre la línea dejando huecos. El
// original arranca prellenado como primera parte (para editarla, no reescribir).

function DividirRenglon({
  versionId,
  item,
  onListo,
}: {
  versionId: string;
  item: ItemRevision;
  onListo: () => void;
}) {
  const router = useRouter();
  const [partes, setPartes] = useState<string[]>([item.texto_original, ""]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validas = partes.map((p) => p.trim()).filter(Boolean);
  // Dividir exige al menos dos partes con texto: una sola sería sólo editar.
  const puedeDividir = validas.length >= 2;

  async function dividir() {
    if (!puedeDividir) {
      setError("Escribí al menos dos partes para dividir el renglón.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      for (const texto of validas) {
        await agregarItemLista(versionId, { texto_original: texto, cantidad: item.cantidad });
      }
      // Solo tras agregar todas las partes se quita el original.
      await quitarItemLista(versionId, item.id);
      onListo();
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo dividir el renglón.");
      setGuardando(false);
    }
  }

  return (
    <div className={styles.altaItem}>
      {partes.map((parte, i) => (
        <label key={i} className={styles.campo}>
          <span>Parte {i + 1}</span>
          <input
            value={parte}
            onChange={(e) =>
              setPartes((ps) => ps.map((p, j) => (j === i ? e.target.value : p)))
            }
            placeholder="Ej. 1 cuaderno cuadriculado grande"
            disabled={guardando}
          />
        </label>
      ))}
      {error ? <p className={styles.itemError}>{error}</p> : null}
      <div className={styles.itemAcciones}>
        <button
          type="button"
          className={styles.botonMini}
          onClick={() => setPartes((ps) => [...ps, ""])}
          disabled={guardando}
        >
          + Otra parte
        </button>
        <button
          type="button"
          className={styles.principal}
          onClick={dividir}
          disabled={guardando || !puedeDividir}
        >
          {guardando ? "Dividiendo…" : `Dividir en ${validas.length}`}
        </button>
      </div>
    </div>
  );
}

// -------------------------------------------------------------- alta de renglón

function AltaRenglon({ versionId, revisada }: { versionId: string; revisada: boolean }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function agregar() {
    setGuardando(true);
    setError(null);
    const item: ItemListaEditable = { texto_original: texto.trim() };
    const cantidadNum = Number(cantidad);
    if (Number.isFinite(cantidadNum)) item.cantidad = cantidadNum;
    try {
      await agregarItemLista(versionId, item);
      setTexto("");
      setCantidad("1");
      setAbierto(false);
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo agregar el ítem.");
    } finally {
      setGuardando(false);
    }
  }

  if (!abierto) {
    return (
      <button
        type="button"
        className={styles.botonMini}
        onClick={() => setAbierto(true)}
        disabled={revisada}
      >
        + Agregar un ítem que faltó
      </button>
    );
  }

  return (
    <div className={styles.altaItem}>
      <label className={styles.campo}>
        <span>Texto del renglón</span>
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Ej. 2 cuadernos cuadriculados grandes"
          disabled={guardando}
        />
      </label>
      <label className={styles.campo}>
        <span>Cantidad</span>
        <input
          type="number"
          min={0}
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          disabled={guardando}
        />
      </label>
      {error ? <p className={styles.itemError}>{error}</p> : null}
      <div className={styles.itemAcciones}>
        <button
          type="button"
          className={styles.principal}
          onClick={agregar}
          disabled={guardando || !texto.trim()}
        >
          {guardando ? "Agregando…" : "Agregar ítem"}
        </button>
        <button type="button" className={styles.botonMini} onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
