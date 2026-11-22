"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  serializarAtributos,
  type ConceptoCreado,
  type ItemListaEditable,
  type ItemRevision,
  type ModoAdquisicion,
  type PropuestaRevision,
} from "@tukit/contrato";
import { editarItemLista, quitarItemLista, FalloListas } from "@/lib/api-listas";
import {
  filasDeExigencia,
  resumenExigido,
  mismosAtributos,
  paresCurados,
  type FilaExigencia,
} from "@/lib/atributos-renglon";
import type { OpcionConcepto } from "./PanelReclasificar";
import AtributosRenglon from "./AtributosRenglon";
import NuevoConcepto from "./NuevoConcepto";
import Desplegable from "./Desplegable";
import type { VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import styles from "@/app/onboarding/Onboarding.module.css";
import DividirRenglon from "./DividirRenglon";

export const MODOS_DIRECTOS: { valor: ModoAdquisicion; etiqueta: string }[] = [
  { valor: "venta_directa_editorial", etiqueta: "Venta directa de la editorial" },
  { valor: "edicion_exclusiva", etiqueta: "Edición exclusiva del colegio" },
  { valor: "plataforma", etiqueta: "Plataforma / licencia digital" },
  { valor: "diferido", etiqueta: "Diferido (lo pide durante el año)" },
];

export const VALORES_DIRECTOS = new Set<string>(MODOS_DIRECTOS.map((m) => m.valor));

export default function RenglonEditable({
  versionId,
  revisada,
  item,
  candidatos,
  conceptos,
  vocabulario,
  sugerencias,
  onConceptoCreado,
}: {
  versionId: string;
  revisada: boolean;
  item: ItemRevision;
  candidatos: PropuestaRevision[];
  conceptos: OpcionConcepto[];
  vocabulario: VocabularioConceptos;
  sugerencias: Record<string, string[]>;
  onConceptoCreado: (creado: ConceptoCreado) => void;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [creandoConcepto, setCreandoConcepto] = useState(false);
  const [dividiendo, setDividiendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [texto, setTexto] = useState(item.texto_original);
  const [concepto, setConcepto] = useState(item.concepto_codigo ?? "");
  const [cantidad, setCantidad] = useState(String(item.cantidad));
  const modoGuardado = VALORES_DIRECTOS.has(item.modo_adquisicion ?? "") ? item.modo_adquisicion! : "";
  const [modo, setModo] = useState<ModoAdquisicion | "">(modoGuardado);
  const [instruccion, setInstruccion] = useState(item.instruccion_colegio ?? "");
  const [filasAtributos, setFilasAtributos] = useState<FilaExigencia[]>(() =>
    filasDeExigencia(item),
  );
  const conceptoCambiado = concepto !== (item.concepto_codigo ?? "");
  const exige = resumenExigido(filasDeExigencia(item));

  const esDirecto = VALORES_DIRECTOS.has(modo);

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
    const cambios: ItemListaEditable = {};
    if (texto.trim() !== item.texto_original) cambios.texto_original = texto.trim();
    if (concepto !== (item.concepto_codigo ?? "")) cambios.concepto = concepto || null;
    const cantidadNum = Number(cantidad);
    if (Number.isFinite(cantidadNum) && cantidadNum !== item.cantidad) cambios.cantidad = cantidadNum;
    if (modo !== modoGuardado) cambios.modo_adquisicion = modo || "mercado_abierto";
    if (instruccion !== (item.instruccion_colegio ?? ""))
      cambios.instruccion_colegio = instruccion || null;
    if (!conceptoCambiado && item.concepto_codigo) {
      const curados = serializarAtributos(paresCurados(filasAtributos));
      if (!mismosAtributos(curados, item.atributos)) cambios.atributos = curados;
    }

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
          {item.concepto_codigo && exige ? (
            <span className={styles.exige}>Exige: {exige}</span>
          ) : null}
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
            if (!abierto) setFilasAtributos(filasDeExigencia(item));
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
          <div className={styles.campo}>
            <span>Concepto (vacío = sin concepto)</span>
            <span className={styles.conceptoFila}>
              <Desplegable
                opciones={[
                  { valor: "", texto: "— sin concepto —" },
                  ...conceptos.map((c) => ({ valor: c.codigo, texto: `${c.nombre} (${c.codigo})` })),
                ]}
                valor={concepto}
                onCambio={setConcepto}
                disabled={guardando}
                buscable
              />
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
          </div>
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
          {!esDirecto && (item.concepto_codigo || concepto) ? (
            <AtributosRenglon
              itemId={item.id}
              filas={filasAtributos}
              onCambio={setFilasAtributos}
              discriminantes={item.atributos_discriminantes}
              porRevisar={item.atributos_por_revisar}
              sugerencias={sugerencias}
              conceptoCambiado={conceptoCambiado}
              disabled={guardando}
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
