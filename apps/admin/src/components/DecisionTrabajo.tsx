"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { EstadoTrabajo } from "@tukit/contrato";
import {
  decidirRevision,
  eliminarTrabajo,
  FalloApi,
  guardarComoCanonico,
} from "@/lib/api-navegador";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  estado: EstadoTrabajo;
  lineasPendientes: number;
  notaRevision: string | null | undefined;
  esPreview?: boolean;
  edicion?: { volverA: string };
}

export default function DecisionTrabajo({
  trabajoId,
  estado,
  lineasPendientes,
  notaRevision,
  esPreview = false,
  edicion,
}: Props) {
  const router = useRouter();
  const [nota, setNota] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const yaPublicado = estado === "publicado";
  const listoParaDecidir = estado === "espera_revision";

  async function decidir(decision: "aprobar" | "devolver"): Promise<void> {
    setError(null);
    setEnviando(true);
    try {
      const conNota = nota.trim() ? { nota: nota.trim() } : {};
      if (decision === "aprobar" && (esPreview || edicion)) {
        await guardarComoCanonico(trabajoId, conNota);
      } else await decidirRevision(trabajoId, { decision, ...conNota });
      setConfirmando(false);
      setNota("");
      if (edicion) router.push(edicion.volverA);
      else router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos guardar la decisión.");
      if (causa instanceof FalloApi && causa.estado === 409) router.refresh();
    } finally {
      setEnviando(false);
    }
  }

  async function descartar(): Promise<void> {
    if (!edicion) return;
    setError(null);
    setEnviando(true);
    try {
      await eliminarTrabajo(trabajoId);
      router.push(edicion.volverA);
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos descartar el borrador.");
      setEnviando(false);
    }
  }

  if (edicion) {
    return (
      <section className={styles.decision} aria-labelledby="decision-titulo">
        <h2 id="decision-titulo">Nueva versión de los kits</h2>
        {yaPublicado ? (
          <p className={styles.publicado}>
            Esta versión ya está publicada: es la que reciben los acudientes que empiecen desde
            ahora. Los que ya habían empezado siguen con la anterior.
          </p>
        ) : (
          <>
            {lineasPendientes > 0 ? (
              <p className={styles.advertencia}>
                Quedan <strong>{lineasPendientes}</strong> líneas sin reconocer o sin validar. Si
                publicas así, el acudiente las va a ver como huecos.
              </p>
            ) : (
              <p className={styles.todoResuelto}>No quedan líneas pendientes en esta versión.</p>
            )}

            <label className={styles.campo} htmlFor="nota-revision">
              Qué cambió en esta versión (opcional, queda en la auditoría)
            </label>
            <textarea
              id="nota-revision"
              rows={2}
              value={nota}
              onChange={(evento) => setNota(evento.target.value)}
              placeholder="Fijé el cuaderno ferrocarril y la plastilina que no se reconocían."
            />

            <div className={styles.decisiones}>
              <div className={styles.opcion}>
                <h3>Publicar esta versión</h3>
                <p>
                  Reemplaza a los kits vigentes del grado. Los acudientes que ya empezaron o
                  pagaron se quedan con la versión anterior. No se avisa a nadie.
                </p>
                {confirmando ? (
                  <div className={styles.confirmacion}>
                    <p>¿Seguro? Desde ahora los acudientes nuevos reciben estos kits.</p>
                    <div className={styles.botonera}>
                      <button
                        type="button"
                        className={styles.principal}
                        disabled={enviando}
                        onClick={() => void decidir("aprobar")}
                      >
                        Sí, publicar
                      </button>
                      <button
                        type="button"
                        className={styles.plano}
                        onClick={() => setConfirmando(false)}
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={styles.principal}
                    disabled={enviando}
                    onClick={() => setConfirmando(true)}
                  >
                    Publicar nueva versión
                  </button>
                )}
              </div>

              <div className={styles.opcion}>
                <h3>Descartar el borrador</h3>
                <p>
                  Borra estos cambios. Los kits vigentes no se tocan en ningún caso.
                </p>
                <button
                  type="button"
                  className={styles.secundario}
                  disabled={enviando}
                  onClick={() => void descartar()}
                >
                  Descartar cambios
                </button>
              </div>
            </div>
          </>
        )}
        {error ? <p className={styles.error}>{error}</p> : null}
      </section>
    );
  }

  return (
    <section className={styles.decision} aria-labelledby="decision-titulo">
      <h2 id="decision-titulo">Decisión de revisión</h2>

      {yaPublicado && esPreview ? (
        <p className={styles.publicado}>
          Estos son los kits canónicos de este grado: la lista quedó aprobada y el acudiente que
          pida su kit sin tope de gasto los recibe al instante, sin volver a optimizar.
        </p>
      ) : yaPublicado ? (
        <p className={styles.publicado}>
          Este trabajo ya se publicó: el acudiente ya vio los kits y ya se le avisó. No se
          puede volver a revisar.
        </p>
      ) : !listoParaDecidir ? (
        <p className={styles.espera}>
          El pipeline todavía no termina (<code>{estado}</code>). La decisión se habilita
          cuando el trabajo llegue a <code>espera_revision</code>.
        </p>
      ) : (
        <>
          {lineasPendientes > 0 ? (
            <p className={styles.advertencia}>
              Quedan <strong>{lineasPendientes}</strong> líneas pendientes. Si{" "}
              {esPreview ? "los guardas" : "publicas"} así, el acudiente las va a ver como huecos o
              como líneas sin resolver.
            </p>
          ) : (
            <p className={styles.todoResuelto}>No quedan líneas pendientes en este trabajo.</p>
          )}

          <label className={styles.campo} htmlFor="nota-revision">
            Nota de la revisión (opcional, queda en la auditoría)
          </label>
          <textarea
            id="nota-revision"
            rows={2}
            value={nota}
            onChange={(evento) => setNota(evento.target.value)}
            placeholder="Cambié los dos textos de lenguaje por la edición 2026."
          />

          <div className={styles.decisiones}>
            <div className={styles.opcion}>
              {esPreview ? (
                <>
                  <h3>Aprobar la lista y guardar estos kits</h3>
                  <p>
                    Aprueba la lista del colegio y deja estos kits, con tus ajustes, como los
                    canónicos del grado. El próximo acudiente sin tope de gasto los recibe al
                    instante. No se avisa a nadie.
                  </p>
                </>
              ) : (
                <>
                  <h3>Publicar al acudiente</h3>
                  <p>
                    Publica sus kits y dispara la notificación. El acudiente se entera y ya
                    no hay vuelta atrás.
                  </p>
                </>
              )}
              {confirmando ? (
                <div className={styles.confirmacion}>
                  <p>
                    {esPreview
                      ? "¿Seguro? La lista queda aprobada para los acudientes y estos kits pasan a ser los del grado."
                      : "¿Seguro? Se le avisa al acudiente y el trabajo sale de la cola."}
                  </p>
                  <div className={styles.botonera}>
                    <button
                      type="button"
                      className={styles.principal}
                      disabled={enviando}
                      onClick={() => void decidir("aprobar")}
                    >
                      {esPreview ? "Sí, aprobar y guardar" : "Sí, publicar y avisar"}
                    </button>
                    <button
                      type="button"
                      className={styles.plano}
                      onClick={() => setConfirmando(false)}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className={styles.principal}
                  disabled={enviando}
                  onClick={() => setConfirmando(true)}
                >
                  {esPreview ? "Aprobar y guardar como canónicos" : "Aprobar y publicar"}
                </button>
              )}
            </div>

            <div className={styles.opcion}>
              <h3>Devolver el trabajo</h3>
              <p>
                Reabre el trabajo para que el pipeline lo vuelva a correr.{" "}
                <strong>Al acudiente no se le avisa nada</strong>: sigue viendo su pantalla de
                espera.
              </p>
              <button
                type="button"
                className={styles.secundario}
                disabled={enviando}
                onClick={() => void decidir("devolver")}
              >
                Devolver sin avisar
              </button>
            </div>
          </div>
        </>
      )}

      {notaRevision ? (
        <p className={styles.notaPrevia}>
          Nota de la última revisión: <q>{notaRevision}</q>
        </p>
      ) : null}
      {error ? <p className={styles.error}>{error}</p> : null}
    </section>
  );
}
