"use client";

// "Mis casos": crear, ver y seguir las solicitudes (PQRS) del acudiente. El
// dueño de cada caso es la sesión (Operación lo verifica); aquí no se pide ni
// se manda ningún correo. Seguir un caso es leer su estado y plazo y agregarle
// mensajes mientras siga abierto.

import Image from "next/image";
import { useState } from "react";
import { MessageSquarePlus, Send } from "lucide-react";
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

export default function MisCasos({ iniciales }: { iniciales: MiCaso[] }) {
  const [casos, setCasos] = useState<MiCaso[]>(iniciales);
  const [formulario, setFormulario] = useState(false);
  const [abierto, setAbierto] = useState<MiCasoDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const [categoria, setCategoria] = useState<CategoriaCaso>("peticion");
  const [asunto, setAsunto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [mensaje, setMensaje] = useState("");

  async function recargar() {
    setCasos(await verMisCasos());
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError(null);
    try {
      await crearCaso({ categoria, asunto, descripcion });
      setAsunto("");
      setDescripcion("");
      setFormulario(false);
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
        <div className={`${styles.vacio} ${styles.vacioCompacto}`}>
          <Image
            src="/marca/caja-abierta.webp"
            alt=""
            width={112}
            height={99}
            className={styles.vacioImagen}
          />
          <div className={styles.vacioTexto}>
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

      {error && (
        <p className={styles.errorPedido} role="alert">
          {error}
        </p>
      )}

      {formulario ? (
        <form className={styles.formCaso} onSubmit={crear}>
          <label>
            Tipo de solicitud
            <select value={categoria} onChange={(e) => setCategoria(e.target.value as CategoriaCaso)}>
              {CATEGORIAS_CASO_ACUDIENTE.map((c) => (
                <option key={c} value={c}>
                  {ETIQUETA_CATEGORIA_CASO[c]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Asunto
            <input value={asunto} onChange={(e) => setAsunto(e.target.value)} maxLength={120} required />
          </label>
          <label>
            Cuéntanos qué pasó
            <textarea
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              rows={4}
              required
            />
          </label>
          <div className={styles.accionesFila}>
            <button type="submit" className={styles.btnPagar} disabled={ocupado}>
              {ocupado ? "Enviando…" : "Abrir caso"}
            </button>
            <button type="button" className={styles.btnCancelar} onClick={() => setFormulario(false)}>
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className={styles.btnNuevoCaso} onClick={() => setFormulario(true)}>
          <MessageSquarePlus size={15} aria-hidden="true" /> Abrir un caso nuevo
        </button>
      )}
    </div>
  );
}
