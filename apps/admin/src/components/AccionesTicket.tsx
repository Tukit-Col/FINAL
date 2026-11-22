"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { EstadoCaso, Prioridad } from "@tukit/contrato";
import {
  ETIQUETA_PRIORIDAD,
  LONGITUD_MAXIMA_RESPUESTA,
  ORDEN_PRIORIDAD,
  TRANSICIONES_CASO,
} from "@tukit/contrato";
import {
  FalloApi,
  agregarNota,
  asignarTicket,
  cambiarEstadoTicket,
  priorizarTicket,
  responderTicket,
  vincularPedidoTicket,
} from "@/lib/api-navegador";
import { rutaSinActivar } from "@/lib/logistica";
import {
  ETIQUETA_ESTADO_TICKET,
  puedeSoltar,
  textoAsignacion,
} from "@/lib/tickets";
import BannerAcceso from "./BannerAcceso";
import styles from "./AccionesTicket.module.css";

const LONGITUD_MAXIMA_NOTA = 2000;
const PRIORIDADES = Object.keys(ORDEN_PRIORIDAD) as Prioridad[];

interface Props {
  casoId: string;
  estado: EstadoCaso;
  pedidoId: string | null;
  puedeAvisar: boolean;
  prioridad: Prioridad;
  asignadoA: string | null;
  yo: string | null;
  esAdmin: boolean;
  urlIngresar?: string;
}

interface Fallo {
  mensaje: string;
  campo: string | null;
  estado: number;
}

export default function AccionesTicket({
  casoId,
  estado,
  pedidoId,
  puedeAvisar,
  prioridad,
  asignadoA,
  yo,
  esAdmin,
  urlIngresar,
}: Props) {
  const router = useRouter();
  const [texto, setTexto] = useState("");
  const [pedido, setPedido] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [nota, setNota] = useState("");
  const [nuevaPrioridad, setNuevaPrioridad] = useState<Prioridad>(prioridad);
  const [confirmaRelevo, setConfirmaRelevo] = useState(false);

  const destinos = TRANSICIONES_CASO[estado];
  const cerrado = estado === "cerrado";

  async function ejecutar(
    accion: () => Promise<unknown>,
    exito: string,
    despues?: () => void,
  ): Promise<void> {
    setFallo(null);
    setAviso(null);
    setEnviando(true);
    try {
      await accion();
      setAviso(exito);
      despues?.();
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        const campo =
          typeof causa.detalle.campo === "string" ? causa.detalle.campo : null;
        const sinActivar = rutaSinActivar(causa.estado);
        setFallo({
          mensaje: sinActivar
            ? "Esta acción se activa al reiniciar el servicio de operación."
            : causa.message,
          campo,
          estado: sinActivar ? 0 : causa.estado,
        });
        if (causa.estado === 409) router.refresh();
      } else {
        setFallo({
          mensaje: "No pudimos completar la acción. Intenta de nuevo.",
          campo: null,
          estado: 0,
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  function responder(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void ejecutar(
      () => responderTicket(casoId, texto),
      puedeAvisar
        ? "Respuesta guardada. Le avisamos al acudiente."
        : "Respuesta guardada. No hay a quién avisar: el caso no tiene titular.",
      () => setTexto(""),
    );
  }

  function vincular(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void ejecutar(
      () => vincularPedidoTicket(casoId, pedido.trim()),
      "Pedido vinculado.",
      () => setPedido(""),
    );
  }

  function guardarNota(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void ejecutar(
      () => agregarNota(casoId, nota),
      "Nota guardada. Solo la ve el equipo.",
      () => setNota(""),
    );
  }

  const invalido = (campo: string) =>
    fallo?.campo === campo ? true : undefined;
  const ajeno = asignadoA !== null && asignadoA !== yo;

  return (
    <section
      className={styles.acciones}
      aria-labelledby="acciones-ticket-titulo"
    >
      <BannerAcceso
        fallo={fallo}
        urlIngresar={urlIngresar}
        onCerrar={() => setFallo(null)}
      />
      <h2 id="acciones-ticket-titulo">Gestionar</h2>

      <div className={styles.barra}>
        <div className={styles.grupo}>
          <span className={styles.etiqueta}>Dueño</span>
          <strong>{textoAsignacion(asignadoA, yo)}</strong>
          {confirmaRelevo ? (
            <>
              <span className={styles.ayuda}>
                Lo tiene otra persona. ¿Lo tomas tú?
              </span>
              <button
                type="button"
                className={styles.principal}
                disabled={enviando}
                onClick={() => {
                  setConfirmaRelevo(false);
                  void ejecutar(
                    () => asignarTicket(casoId, "yo"),
                    "Ticket asignado a ti.",
                  );
                }}
              >
                Sí, tomarlo
              </button>
              <button
                type="button"
                className={styles.secundario}
                onClick={() => setConfirmaRelevo(false)}
              >
                No
              </button>
            </>
          ) : (
            <>
              {asignadoA !== yo ? (
                <button
                  type="button"
                  className={styles.secundario}
                  disabled={enviando}
                  onClick={() =>
                    ajeno
                      ? setConfirmaRelevo(true)
                      : void ejecutar(
                          () => asignarTicket(casoId, "yo"),
                          "Ticket asignado a ti.",
                        )
                  }
                >
                  Asignarme
                </button>
              ) : null}
              {puedeSoltar(asignadoA, yo, esAdmin) ? (
                <button
                  type="button"
                  className={styles.secundario}
                  disabled={enviando}
                  onClick={() =>
                    void ejecutar(
                      () => asignarTicket(casoId, "nadie"),
                      "Ticket liberado.",
                    )
                  }
                >
                  Soltar
                </button>
              ) : null}
            </>
          )}
        </div>

        {!cerrado ? (
          <div className={styles.grupo}>
            <label className={styles.etiqueta} htmlFor="prioridad-ticket">
              Prioridad
            </label>
            <select
              id="prioridad-ticket"
              value={nuevaPrioridad}
              disabled={enviando}
              onChange={(e) => setNuevaPrioridad(e.target.value as Prioridad)}
            >
              {PRIORIDADES.map((p) => (
                <option key={p} value={p}>
                  {ETIQUETA_PRIORIDAD[p]}
                </option>
              ))}
            </select>
            {nuevaPrioridad !== prioridad ? (
              <button
                type="button"
                className={styles.principal}
                disabled={enviando}
                onClick={() =>
                  void ejecutar(
                    () => priorizarTicket(casoId, nuevaPrioridad),
                    `Prioridad: ${ETIQUETA_PRIORIDAD[nuevaPrioridad]}.`,
                  )
                }
              >
                Aplicar
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {cerrado ? (
        <p className={styles.ayuda}>
          El ticket está cerrado: ya no admite respuestas ni cambios.
        </p>
      ) : (
        <form className={styles.formulario} onSubmit={responder}>
          <div className={styles.campo}>
            <label htmlFor="respuesta">Respuesta al acudiente</label>
            <textarea
              id="respuesta"
              rows={4}
              required
              maxLength={LONGITUD_MAXIMA_RESPUESTA}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              aria-invalid={invalido("texto")}
              aria-describedby="respuesta-ayuda"
            />
            <span id="respuesta-ayuda" className={styles.ayuda}>
              {texto.length}/{LONGITUD_MAXIMA_RESPUESTA}. Queda en la historia
              del ticket y al acudiente le llega un aviso; el texto se lee
              dentro de Tukit, no sale por correo ni WhatsApp.
              {puedeAvisar
                ? ""
                : " Este caso no tiene titular: se guarda sin aviso."}
            </span>
          </div>
          <div className={styles.botonera}>
            <button
              type="submit"
              className={styles.principal}
              disabled={enviando || texto.trim() === ""}
            >
              Responder
            </button>
          </div>
        </form>
      )}

      {destinos.length > 0 ? (
        <div className={styles.fila}>
          <span className={styles.etiqueta}>Pasar a</span>
          <div className={styles.botonera}>
            {destinos.map((destino) => (
              <button
                key={destino}
                type="button"
                className={styles.secundario}
                disabled={enviando}
                onClick={() =>
                  void ejecutar(
                    () => cambiarEstadoTicket(casoId, destino),
                    `Ticket: ${ETIQUETA_ESTADO_TICKET[destino]}.`,
                  )
                }
              >
                {ETIQUETA_ESTADO_TICKET[destino]}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <form
        className={`${styles.formulario} ${styles.nota}`}
        onSubmit={guardarNota}
      >
        <div className={styles.campo}>
          <label htmlFor="nota-interna">Nota interna</label>
          <textarea
            id="nota-interna"
            rows={3}
            maxLength={LONGITUD_MAXIMA_NOTA}
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            aria-describedby="nota-ayuda"
          />
          <span id="nota-ayuda" className={styles.ayuda}>
            <strong>Solo el equipo la ve.</strong> El acudiente no la recibe ni
            la lee. {nota.length}/{LONGITUD_MAXIMA_NOTA}.
          </span>
        </div>
        <div className={styles.botonera}>
          <button
            type="submit"
            className={styles.secundario}
            disabled={enviando || nota.trim() === ""}
          >
            Guardar nota
          </button>
        </div>
      </form>

      {pedidoId === null && !cerrado ? (
        <form className={styles.fila} onSubmit={vincular}>
          <label className={styles.etiqueta} htmlFor="pedido-vinculo">
            Vincular pedido
          </label>
          <input
            id="pedido-vinculo"
            value={pedido}
            onChange={(e) => setPedido(e.target.value)}
            placeholder="Id completo del pedido"
            autoComplete="off"
            aria-invalid={invalido("pedido_id")}
          />
          <button
            type="submit"
            className={styles.secundario}
            disabled={enviando || pedido.trim() === ""}
          >
            Vincular
          </button>
        </form>
      ) : null}

      {aviso ? (
        <p className={styles.exito} role="status">
          {aviso}
        </p>
      ) : null}
    </section>
  );
}
