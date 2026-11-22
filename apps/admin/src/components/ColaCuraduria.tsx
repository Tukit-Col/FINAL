"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ImageOff, Trash2 } from "lucide-react";
import { NIVELES, ETIQUETA_NIVEL, serializarAtributos } from "@tukit/contrato";
import type { AprobarPropuesta, Nivel, PropuestaCola } from "@tukit/contrato";
import {
  colaPropuestas,
  aprobarPropuesta,
  rechazarPropuesta,
  FalloCatalogo,
} from "@/lib/api-catalogo";
import {
  conCampo,
  conValor,
  filasDeAtributos,
  pareceUrl,
  type ParAtributo,
} from "@/lib/atributos-editor";
import GrupoAtributos from "./GrupoAtributos";
import type { OpcionConcepto } from "./PanelReclasificar";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

interface Props {
  conceptos: OpcionConcepto[];
  personajes: string[];
}

function nombreConcepto(p: PropuestaCola): string {
  if ("codigo" in p.concepto) return `${p.concepto.nombre} (${p.concepto.codigo})`;
  return p.concepto.sugerido ? `sugerido: ${p.concepto.sugerido}` : "sin concepto";
}

function codigoConcepto(p: PropuestaCola): string | null {
  return "codigo" in p.concepto ? p.concepto.codigo : null;
}

function precioTexto(precio: number | null): string {
  if (precio === null) return "sin precio";
  return `$${precio.toLocaleString("es-CO")}`;
}

export default function ColaCuraduria({ conceptos, personajes }: Props) {
  const [propuestas, setPropuestas] = useState<PropuestaCola[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ocupada, setOcupada] = useState<string | null>(null);

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

  useEffect(() => {
    const t = setTimeout(() => void recargar(), 0);
    return () => clearTimeout(t);
  }, [recargar]);

  const aprobar = useCallback(
    async (p: PropuestaCola, cuerpo: AprobarPropuesta) => {
      setError(null);
      setOcupada(p.id);
      try {
        await aprobarPropuesta(p.id, cuerpo);
        await recargar();
      } catch (causa) {
        setError(
          causa instanceof FalloCatalogo ? causa.message : "No pudimos aprobar la propuesta.",
        );
      } finally {
        setOcupada(null);
      }
    },
    [recargar],
  );

  const rechazar = useCallback(
    async (p: PropuestaCola, motivo: string | undefined, noSurtir: boolean) => {
      setError(null);
      setOcupada(p.id);
      try {
        await rechazarPropuesta(p.id, {
          motivo: motivo?.trim() || undefined,
          no_surtir: noSurtir || undefined,
        });
        await recargar();
      } catch (causa) {
        setError(
          causa instanceof FalloCatalogo ? causa.message : "No pudimos rechazar la propuesta.",
        );
      } finally {
        setOcupada(null);
      }
    },
    [recargar],
  );

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
        <FilaPropuesta
          key={p.id}
          p={p}
          conceptos={conceptos}
          personajes={personajes}
          ocupada={ocupada === p.id}
          onAprobar={aprobar}
          onRechazar={rechazar}
        />
      ))}
    </section>
  );
}

interface FilaProps {
  p: PropuestaCola;
  conceptos: OpcionConcepto[];
  personajes: string[];
  ocupada: boolean;
  onAprobar: (p: PropuestaCola, cuerpo: AprobarPropuesta) => void;
  onRechazar: (p: PropuestaCola, motivo: string | undefined, noSurtir: boolean) => void;
}

function FilaPropuesta({ p, conceptos, personajes, ocupada, onAprobar, onRechazar }: FilaProps) {
  const [nivel, setNivel] = useState<Nivel>((p.nivel_sugerido as Nivel) ?? "confiable");

  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(p.nombre);
  const [marca, setMarca] = useState(p.marca ?? "");
  const [personaje, setPersonaje] = useState("");
  const [imagenUrl, setImagenUrl] = useState(p.imagen_url ?? "");

  const conceptoDeLaPropuesta = useMemo(
    () => conceptos.find((c) => c.codigo === codigoConcepto(p)),
    [conceptos, p],
  );
  const gruposIniciales = useMemo(
    () =>
      filasDeAtributos(
        p.atributos_al_aprobar ?? p.atributos_verificados ?? {},
        conceptoDeLaPropuesta?.atributos_discriminantes ?? [],
        conceptoDeLaPropuesta?.atributos_descriptivos ?? [],
      ),
    [conceptoDeLaPropuesta, p.atributos_al_aprobar, p.atributos_verificados],
  );
  const [discriminantes, setDiscriminantes] = useState<ParAtributo[]>(
    gruposIniciales.discriminantes,
  );
  const [descriptivos, setDescriptivos] = useState<ParAtributo[]>(gruposIniciales.descriptivos);
  const [libres, setLibres] = useState<ParAtributo[]>(gruposIniciales.libres);

  const [rechazando, setRechazando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [noSurtir, setNoSurtir] = useState(false);

  const urlValida = useMemo(() => pareceUrl(imagenUrl), [imagenUrl]);
  const puedeAprobar = !ocupada && nombre.trim().length > 0 && urlValida;

  function construirCuerpo(): AprobarPropuesta {
    const cuerpo: AprobarPropuesta = { nivel };
    if (!editando) return cuerpo;

    const nombreLimpio = nombre.trim();
    if (nombreLimpio && nombreLimpio !== p.nombre) cuerpo.nombre = nombreLimpio;

    const marcaLimpia = marca.trim() ? marca.trim() : null;
    if (marcaLimpia !== (p.marca ?? null)) cuerpo.marca = marcaLimpia;

    const imagenLimpia = imagenUrl.trim() ? imagenUrl.trim() : null;
    if (imagenLimpia !== (p.imagen_url ?? null)) cuerpo.imagen_url = imagenLimpia;

    if (personaje.trim()) cuerpo.personaje = personaje.trim();

    const mapa = serializarAtributos([...discriminantes, ...descriptivos, ...libres]);
    const inicial = serializarAtributos([
      ...gruposIniciales.discriminantes,
      ...gruposIniciales.descriptivos,
      ...gruposIniciales.libres,
    ]);
    if (Object.keys(mapa).length > 0 && JSON.stringify(mapa) !== JSON.stringify(inicial)) {
      cuerpo.atributos = mapa;
    }

    return cuerpo;
  }

  const editarLibre = (indice: number, campo: keyof ParAtributo, valor: string) =>
    setLibres((prev) => conCampo(prev, indice, campo, valor));

  return (
    <div className={styles.panel}>
      <header className={styles.panelCabecera}>
        <div style={{ display: "flex", gap: "var(--espacio-3)", alignItems: "center" }}>
          {p.imagen_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.previa} src={p.imagen_url} alt="" />
          ) : (
            <span className={styles.previaVacia}>
              <ImageOff size={22} aria-hidden="true" />
            </span>
          )}
          <div>
            <h2>{p.nombre}</h2>
            <span className={styles.panelSku}>
              {p.id_corto} · {nombreConcepto(p)} · {precioTexto(p.precio)}
              {p.marca ? ` · ${p.marca}` : ""} · origen {p.origen}
            </span>
          </div>
        </div>
      </header>

      <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
        <label className={styles.bandera}>
          Nivel
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
          className={styles.secundario}
          disabled={ocupada}
          onClick={() => setEditando((v) => !v)}
          aria-expanded={editando}
        >
          {editando ? "Ocultar detalles" : "Editar detalles"}
        </button>
        <button
          type="button"
          className={styles.principal}
          disabled={!puedeAprobar}
          onClick={() => onAprobar(p, construirCuerpo())}
        >
          {ocupada ? "…" : "Aprobar"}
        </button>
        {!rechazando && (
          <button
            type="button"
            className={styles.peligro}
            disabled={ocupada}
            onClick={() => {
              setRechazando(true);
              setMotivo("");
              setNoSurtir(false);
            }}
          >
            Rechazar
          </button>
        )}
      </div>

      {editando && (
        <div className={styles.rejilla}>
          <div className={`${styles.campo} ${styles.campoAncho}`}>
            <label htmlFor={`cola-nombre-${p.id}`}>Nombre</label>
            <input
              id={`cola-nombre-${p.id}`}
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
            {nombre.trim().length === 0 && (
              <span className={`${styles.ayuda} ${styles.ayudaError}`}>
                El nombre no puede quedar vacío.
              </span>
            )}
          </div>

          <div className={styles.campo}>
            <label htmlFor={`cola-marca-${p.id}`}>Marca</label>
            <input
              id={`cola-marca-${p.id}`}
              value={marca}
              onChange={(e) => setMarca(e.target.value)}
              placeholder="sin marca"
            />
          </div>

          <div className={styles.campo}>
            <label htmlFor={`cola-personaje-${p.id}`}>Personaje</label>
            <input
              id={`cola-personaje-${p.id}`}
              list={`cola-personajes-${p.id}`}
              value={personaje}
              onChange={(e) => setPersonaje(e.target.value)}
              placeholder="lo saca del nombre si lo dejás vacío"
            />
            <datalist id={`cola-personajes-${p.id}`}>
              {personajes.map((n) => (
                <option key={n} value={n} />
              ))}
            </datalist>
          </div>

          <span className={styles.subtitulo}>Imagen</span>
          <div className={styles.imagenBloque}>
            <div className={`${styles.campo} ${styles.imagenCampo}`}>
              <label htmlFor={`cola-imagen-${p.id}`}>URL de la imagen</label>
              <input
                id={`cola-imagen-${p.id}`}
                value={imagenUrl}
                onChange={(e) => setImagenUrl(e.target.value)}
                placeholder="https://…"
              />
              {!urlValida && (
                <span className={`${styles.ayuda} ${styles.ayudaError}`}>
                  Tiene que ser una URL http(s) válida.
                </span>
              )}
            </div>
            {imagenUrl.trim() && urlValida ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className={styles.previa} src={imagenUrl} alt="Vista previa" />
            ) : (
              <span className={styles.previaVacia}>Sin imagen</span>
            )}
          </div>

          <span className={styles.subtitulo}>Atributos</span>
          {!conceptoDeLaPropuesta && (
            <span className={styles.ayuda}>
              El concepto todavía no está confirmado; agregá atributos libres si hace falta.
            </span>
          )}
          <GrupoAtributos
            titulo="Filtra la búsqueda"
            nota="estos atributos deciden qué candidatos entran a un kit."
            filas={discriminantes}
            onEditar={(i, valor) => setDiscriminantes((prev) => conValor(prev, i, valor))}
          />
          <GrupoAtributos
            titulo="Solo informativo"
            nota="se le muestran al acudiente pero no filtran."
            filas={descriptivos}
            onEditar={(i, valor) => setDescriptivos((prev) => conValor(prev, i, valor))}
          />

          <div className={styles.atributos}>
            {libres.length > 0 && (
              <span className={styles.ayuda}>
                <strong>Otros</strong> — claves que este concepto no declara.
              </span>
            )}
            {libres.map((par, i) => (
              <div key={i} className={styles.atributoFila}>
                <input
                  aria-label="Clave"
                  placeholder="clave"
                  value={par.clave}
                  onChange={(e) => editarLibre(i, "clave", e.target.value)}
                />
                <input
                  aria-label="Valor"
                  placeholder="valor"
                  value={par.valor}
                  onChange={(e) => editarLibre(i, "valor", e.target.value)}
                />
                <button
                  type="button"
                  className={styles.secundario}
                  onClick={() => setLibres((prev) => prev.filter((_, j) => j !== i))}
                  aria-label="Quitar atributo"
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </div>
            ))}
            <button
              type="button"
              className={styles.secundario}
              style={{ alignSelf: "flex-start" }}
              onClick={() => setLibres((prev) => [...prev, { clave: "", valor: "" }])}
            >
              + Atributo
            </button>
          </div>

          <span className={styles.ayuda} style={{ gridColumn: "1 / -1" }}>
            Solo se guardan los campos que cambiés; el resto lo completa el sistema al aprobar.
          </span>
        </div>
      )}

      {rechazando && (
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
              disabled={ocupada}
              onClick={() => onRechazar(p, motivo, noSurtir)}
            >
              {ocupada ? "…" : "Confirmar rechazo"}
            </button>
            <button
              type="button"
              className={styles.secundario}
              disabled={ocupada}
              onClick={() => setRechazando(false)}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
