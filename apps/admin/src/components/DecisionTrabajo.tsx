"use client";

// AD-06 — la decision sobre el trabajo entero.
//
// Las dos opciones se ven distinto a proposito, porque lo que hacen es
// distinto y no al reves: aprobar publica los kits Y dispara la notificacion
// al acudiente, o sea que sale del sistema y ya no se puede recoger; devolver
// reabre el trabajo y el acudiente no se entera. Ponerlas como dos botones
// gemelos seria invitar a publicar por inercia.

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { EstadoTrabajo } from "@tukit/contrato";
import { decidirRevision, FalloApi } from "@/lib/api-navegador";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  estado: EstadoTrabajo;
  lineasPendientes: number;
  notaRevision: string | null | undefined;
}

export default function DecisionTrabajo({
  trabajoId,
  estado,
  lineasPendientes,
  notaRevision,
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
      await decidirRevision(trabajoId, {
        decision,
        ...(nota.trim() ? { nota: nota.trim() } : {}),
      });
      setConfirmando(false);
      setNota("");
      router.refresh();
    } catch (causa) {
      // El 409 `trabajo_ya_publicado` llega aqui cuando alguien publico el
      // mismo trabajo desde otra pestana. Se muestra su mensaje y el refresco
      // deja los botones apagados.
      setError(causa instanceof FalloApi ? causa.message : "No pudimos guardar la decisión.");
      if (causa instanceof FalloApi && causa.estado === 409) router.refresh();
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className={styles.decision} aria-labelledby="decision-titulo">
      <h2 id="decision-titulo">Decisión de revisión</h2>

      {yaPublicado ? (
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
              Quedan <strong>{lineasPendientes}</strong> líneas pendientes. Si publicas así, el
              acudiente las va a ver como huecos o como líneas sin resolver.
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
              <h3>Publicar al acudiente</h3>
              <p>
                Publica los tres kits y dispara la notificación. El acudiente se entera y ya no
                hay vuelta atrás.
              </p>
              {confirmando ? (
                <div className={styles.confirmacion}>
                  {/* Sin identificar al acudiente: el nombre va cifrado y la
                      consola es libre de PII (ver page.tsx). Antes se mostraba
                      un trozo del id del TRABAJO mal rotulado como acudiente. */}
                  <p>¿Seguro? Se le avisa al acudiente y el trabajo sale de la cola.</p>
                  <div className={styles.botonera}>
                    <button
                      type="button"
                      className={styles.principal}
                      disabled={enviando}
                      onClick={() => void decidir("aprobar")}
                    >
                      Sí, publicar y avisar
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
                  Aprobar y publicar
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
