"use client";

// "Mis casos": crear, ver y seguir las solicitudes (PQRS) del acudiente. El
// dueño de cada caso es la sesión (Operación lo verifica); aquí no se pide ni
// se manda ningún correo. Seguir un caso es leer su estado y plazo y agregarle
// mensajes mientras siga abierto.

import { useId, useState } from "react";
import { CheckCircle2, LifeBuoy, MessageSquarePlus, Send } from "lucide-react";
import {
  CATEGORIAS_CASO_ACUDIENTE,
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_ESTADO_CASO,
  type CategoriaCaso,
  type MiCaso,
  type MiCasoDetalle,
} from "@tukit/contrato";
import { comentarMiCaso, crearCaso, FalloApi, verMiCaso, verMisCasos } from "@/lib/api-navegador";
import { fechaYHora } from "@/lib/retracto";
import styles from "./Dashboard.module.css";

const CERRADOS = new Set(["resuelto", "cerrado"]);
const MAX_ASUNTO = 120;
const MAX_DESCRIPCION = 2000;

export default function MisCasos({
  iniciales,
  formularioInicial = false,
}: {
  iniciales: MiCaso[];
  /** Solo para pruebas visuales: arranca con el formulario abierto. */
  formularioInicial?: boolean;
}) {
  const idForm = useId();
  const [casos, setCasos] = useState<MiCaso[]>(iniciales);
  const [formulario, setFormulario] = useState(formularioInicial);
  const [creado, setCreado] = useState(false);
  const [abierto, setAbierto] = useState<MiCasoDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const [categoria, setCategoria] = useState<CategoriaCaso>("peticion");
  const [asunto, setAsunto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [mensaje, setMensaje] = useState("");

  const valido = asunto.trim().length >= 3 && descripcion.trim().length >= 10;

  async function recargar() {
    setCasos(await verMisCasos());
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError(null);
    try {
      await crearCaso({ categoria, asunto: asunto.trim(), descripcion: descripcion.trim() });
      setAsunto("");
      setDescripcion("");
      setFormulario(false);
      setCreado(true);
      await recargar();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos crear tu caso. Intenta de nuevo.");
    } finally {
      setOcupado(false);
    }
  }

  async function ver(casoId: string) {
    if (abierto?.caso_id === casoId) {
      setAbierto(null);
      return;
    }
    setError(null);
    try {
      setAbierto(await verMiCaso(casoId));
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos abrir el caso.");
    }
  }

  async function responder(e: React.FormEvent) {
    e.preventDefault();
    if (!abierto || !mensaje.trim()) return;
    setOcupado(true);
    setError(null);
    try {
      await comentarMiCaso(abierto.caso_id, mensaje.trim());
      setMensaje("");
      setAbierto(await verMiCaso(abierto.caso_id));
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos enviar tu mensaje.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.casos}>
      {casos.length === 0 && !formulario && (
        <div className={styles.casosVacio}>
          <span className={styles.casosVacioIcono} aria-hidden="true">
            <LifeBuoy size={36} strokeWidth={1.5} />
          </span>
          <div className={styles.casosVacioTexto}>
            <p className={styles.vacioTitulo}>Sin casos abiertos</p>
            <p>
              Si tienes un problema con un pedido, una duda o una idea, ábrelo aquí y te
              respondemos.
            </p>
          </div>
        </div>
      )}

      {casos.length > 0 && (
        <ul className={styles.listaCasos}>
          {casos.map((caso) => (
            <li key={caso.caso_id} className={styles.casoItem}>
              <button
                type="button"
                className={styles.casoCabecera}
                aria-expanded={abierto?.caso_id === caso.caso_id}
                onClick={() => void ver(caso.caso_id)}
              >
                <span className={styles.casoAsunto}>{caso.asunto}</span>
                <span className={styles.casoMeta}>
                  {ETIQUETA_CATEGORIA_CASO[caso.categoria]} · abierto el {fechaYHora(caso.abierto_en)}
                </span>
                <span
                  className={`${styles.badge} ${CERRADOS.has(caso.estado) ? styles.badgeExito : styles.badgeAviso}`}
                >
                  <span className={styles.badgeDot} />
                  {ETIQUETA_ESTADO_CASO[caso.estado]}
                </span>
              </button>

              {abierto?.caso_id === caso.caso_id && (
                <div className={styles.casoDetalle}>
                  <p>{abierto.descripcion}</p>
                  {abierto.vence_en && !CERRADOS.has(abierto.estado) && (
                    <p className={styles.notaRetracto}>
                      Te respondemos a más tardar el {fechaYHora(abierto.vence_en)}.
                    </p>
                  )}
                  {abierto.comentarios.length > 0 && (
                    <ul className={styles.mensajes} aria-label="Conversación del caso">
                      {abierto.comentarios.map((c, i) => (
                        <li key={i}>
                          <strong>{c.autor === "equipo" ? "Equipo Tukit" : "Tú"}</strong>
                          <span>{c.texto}</span>
                          <time dateTime={c.creado_en}>{fechaYHora(c.creado_en)}</time>
                        </li>
                      ))}
                    </ul>
                  )}
                  {!CERRADOS.has(abierto.estado) ? (
                    <form className={styles.formMensaje} onSubmit={responder}>
                      <label>
                        Agregar un mensaje
                        <textarea
                          value={mensaje}
                          onChange={(e) => setMensaje(e.target.value)}
                          rows={2}
                          maxLength={1000}
                          required
                        />
                      </label>
                      <button type="submit" className={styles.btnPagar} disabled={ocupado}>
                        <Send size={14} aria-hidden="true" /> Enviar mensaje
                      </button>
                    </form>
                  ) : (
                    <p className={styles.notaRetracto}>
                      Este caso está cerrado. Si el problema sigue, abre uno nuevo.
                    </p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && !formulario && (
        <p className={styles.errorPedido} role="alert">
          {error}
        </p>
      )}

      {creado && !formulario && (
        <p className={styles.exitoCaso} role="status">
          <CheckCircle2 size={16} aria-hidden="true" /> Recibimos tu caso. Te respondemos por aquí.
        </p>
      )}

      {formulario ? (
        <form className={styles.formCaso} onSubmit={crear} aria-busy={ocupado}>
          <div className={styles.campo}>
            <label htmlFor={`${idForm}-tipo`}>Tipo de solicitud</label>
            <select
              id={`${idForm}-tipo`}
              value={categoria}
              onChange={(e) => setCategoria(e.target.value as CategoriaCaso)}
            >
              {CATEGORIAS_CASO_ACUDIENTE.map((c) => (
                <option key={c} value={c}>
                  {ETIQUETA_CATEGORIA_CASO[c]}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campo}>
            <label htmlFor={`${idForm}-asunto`}>Asunto</label>
            <input
              id={`${idForm}-asunto`}
              value={asunto}
              onChange={(e) => setAsunto(e.target.value)}
              maxLength={MAX_ASUNTO}
              placeholder="Ej. Mi pedido llegó incompleto"
              autoComplete="off"
              required
            />
          </div>
          <div className={styles.campo}>
            <label htmlFor={`${idForm}-desc`}>Cuéntanos qué pasó</label>
            <textarea
              id={`${idForm}-desc`}
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              rows={4}
              maxLength={MAX_DESCRIPCION}
              placeholder="Con los detalles que tengas (número de pedido, producto, fecha) respondemos más rápido."
              aria-describedby={`${idForm}-cuenta`}
              required
            />
            <span id={`${idForm}-cuenta`} className={styles.contador}>
              {descripcion.length} / {MAX_DESCRIPCION}
            </span>
          </div>
          {error && (
            <p className={styles.errorPedido} role="alert">
              {error}
            </p>
          )}
          <div className={styles.accionesFila}>
            <button type="submit" className={styles.btnPagar} disabled={ocupado || !valido}>
              <Send size={14} aria-hidden="true" /> {ocupado ? "Enviando…" : "Abrir caso"}
            </button>
            <button
              type="button"
              className={styles.btnCancelar}
              disabled={ocupado}
              onClick={() => {
                setFormulario(false);
                setError(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          className={styles.btnNuevoCaso}
          onClick={() => {
            setCreado(false);
            setFormulario(true);
          }}
        >
          <MessageSquarePlus size={15} aria-hidden="true" /> Abrir un caso nuevo
        </button>
      )}
    </div>
  );
}
